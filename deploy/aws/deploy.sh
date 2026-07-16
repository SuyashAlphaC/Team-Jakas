#!/usr/bin/env bash
# Deploy FastAPI backend to AWS App Runner (ECR + managed container service).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REPO_NAME="${ECR_REPO:-context-aware-observability}"
SERVICE_NAME="${APP_RUNNER_SERVICE:-context-aware-observability-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECR_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"
ROLE_NAME="${APP_RUNNER_ECR_ROLE:-AppRunnerECRAccessRole}"

echo "==> Region: ${REGION}  Account: ${ACCOUNT}"
echo "==> Image: ${ECR_URI}"

echo "==> Ensure ECR repository"
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${REGION}" >/dev/null

echo "==> Docker login to ECR"
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

echo "==> Build image (includes ML models + fixtures)"
docker build -f "${ROOT}/backend/Dockerfile" -t "${REPO_NAME}:${IMAGE_TAG}" "${ROOT}"
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${ECR_URI}"

echo "==> Push to ECR"
docker push "${ECR_URI}"

echo "==> Ensure App Runner ECR access role"
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "build.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'
ACCESS_ROLE_ARN="$(aws iam get-role --role-name "${ROLE_NAME}" --query Role.Arn --output text 2>/dev/null || true)"
if [[ -z "${ACCESS_ROLE_ARN}" ]]; then
  ACCESS_ROLE_ARN="$(aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    --query Role.Arn --output text)"
  aws iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
  echo "    Created role ${ACCESS_ROLE_ARN}"
  sleep 10
else
  echo "    Using role ${ACCESS_ROLE_ARN}"
fi

INSTANCE_ROLE_ARN="$(aws iam get-role --role-name "${ROLE_NAME}-instance" --query Role.Arn --output text 2>/dev/null || true)"
if [[ -z "${INSTANCE_ROLE_ARN}" ]]; then
  INSTANCE_TRUST='{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "tasks.apprunner.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
  INSTANCE_ROLE_ARN="$(aws iam create-role \
    --role-name "${ROLE_NAME}-instance" \
    --assume-role-policy-document "${INSTANCE_TRUST}" \
    --query Role.Arn --output text)"
  sleep 5
fi

SERVICE_JSON="$(aws apprunner list-services --region "${REGION}" --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text 2>/dev/null || true)"

SOURCE_CONFIG=$(cat <<EOF
{
  "ImageRepository": {
    "ImageIdentifier": "${ECR_URI}",
    "ImageConfiguration": {
      "Port": "8000",
      "RuntimeEnvironmentVariables": {
        "OBS_USE_ML": "true",
        "ALLOWED_ORIGINS": "*"
      }
    },
    "ImageRepositoryType": "ECR"
  },
  "AuthenticationConfiguration": {
    "AccessRoleArn": "${ACCESS_ROLE_ARN}"
  },
  "AutoDeploymentsEnabled": false
}
EOF
)

INSTANCE_CONFIG='{"Cpu":"2048","Memory":"4096","InstanceRoleArn":"'"${INSTANCE_ROLE_ARN}"'"}'
HEALTH_CONFIG='{"Protocol":"HTTP","Path":"/health","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}'

if [[ -n "${SERVICE_JSON}" && "${SERVICE_JSON}" != "None" ]]; then
  echo "==> Update App Runner service ${SERVICE_NAME}"
  aws apprunner update-service \
    --region "${REGION}" \
    --service-arn "${SERVICE_JSON}" \
    --source-configuration "${SOURCE_CONFIG}" \
    --instance-configuration "${INSTANCE_CONFIG}" \
    --health-check-configuration "${HEALTH_CONFIG}" \
    --query "Service.ServiceUrl" --output text >/dev/null
  SERVICE_ARN="${SERVICE_JSON}"
else
  echo "==> Create App Runner service ${SERVICE_NAME}"
  SERVICE_ARN="$(aws apprunner create-service \
    --region "${REGION}" \
    --service-name "${SERVICE_NAME}" \
    --source-configuration "${SOURCE_CONFIG}" \
    --instance-configuration "${INSTANCE_CONFIG}" \
    --health-check-configuration "${HEALTH_CONFIG}" \
    --query "Service.ServiceArn" --output text)"
fi

echo "==> Waiting for service to reach RUNNING (may take 5–10 min)…"
for i in $(seq 1 60); do
  STATUS="$(aws apprunner describe-service --region "${REGION}" --service-arn "${SERVICE_ARN}" --query "Service.Status" --output text)"
  URL="$(aws apprunner describe-service --region "${REGION}" --service-arn "${SERVICE_ARN}" --query "Service.ServiceUrl" --output text)"
  echo "    [${i}/60] status=${STATUS} url=https://${URL}"
  if [[ "${STATUS}" == "RUNNING" ]]; then
    echo ""
    echo "Backend URL: https://${URL}"
    curl -sf "https://${URL}/health" && echo ""
    echo "${URL}" > "${ROOT}/deploy/aws/.backend-url"
    exit 0
  fi
  if [[ "${STATUS}" == "CREATE_FAILED" || "${STATUS}" == "UPDATE_FAILED" ]]; then
    aws apprunner describe-service --region "${REGION}" --service-arn "${SERVICE_ARN}" --query "Service" --output json
    exit 1
  fi
  sleep 15
done
echo "Timed out waiting for App Runner"
exit 1
