import os
import logging

logger = logging.getLogger(__name__)

def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """Fetch a secret from Google Cloud Secret Manager.
    
    Falls back to environment variables if the client library is not installed,
    if credentials are not configured, or if the GCP call fails.
    """
    gcp_project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not gcp_project:
        # No GCP project specified, fall back immediately to env var
        return os.getenv(secret_name, default)

    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{gcp_project}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8").strip()
        logger.info(f"Loaded secret {secret_name} successfully from GCP Secret Manager.")
        return secret_value
    except ImportError:
        logger.debug("google-cloud-secret-manager is not installed. Using local environment variables.")
    except Exception as e:
        logger.debug(f"Failed to load secret {secret_name} from GCP Secret Manager ({e}). Using local fallback.")
    
    return os.getenv(secret_name, default)
