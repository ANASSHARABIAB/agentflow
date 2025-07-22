import os
import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage, firestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure your buckets
USER_BUCKET = os.environ.get("USER_BUCKET", "agentflow-466510-user-data")
SHARED_BUCKET = os.environ.get("SHARED_BUCKET", "agentflow-466510-shared-knowledgebase")

# Initialize clients - try different approaches for Cloud Run
def init_clients():
    try:
        # Try with service account key first
        sa_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if sa_key_path and os.path.exists(sa_key_path):
            logger.info(f"Using service account key: {sa_key_path}")
            storage_client = storage.Client.from_service_account_json(sa_key_path)
            firestore_client = firestore.Client.from_service_account_json(sa_key_path)
        else:
            # Fall back to default credentials
            logger.info("Using default credentials")
            storage_client = storage.Client()
            firestore_client = firestore.Client()
        
        return storage_client, firestore_client
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        # Still return clients, let individual operations fail with better error messages
        return storage.Client(), firestore.Client()

storage_client, firestore_client = init_clients()

app = FastAPI(title="AgentFlow Upload Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # For dev; lock down in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

class UploadUrlRequest(BaseModel):
    user_id: str | None = None
    filename: str
    content_type: str = "application/octet-stream"
    upload_type: str  # one of: "shared_knowledge", "shared_prompts", "user_document", "user_prompt"

class ConfirmUploadRequest(BaseModel):
    upload_id: str
    status: str = "completed"

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "agentflow-upload-service",
        "version": "1.0.0",
        "buckets": {
            "user_bucket": USER_BUCKET,
            "shared_bucket": SHARED_BUCKET
        }
    }

@app.get("/health")
def health():
    """Alternative health endpoint"""
    return {"status": "ok"}

@app.post("/upload-url")
def generate_upload_url(req: UploadUrlRequest):
    logger.info(f"Generating upload URL for {req.upload_type}: {req.filename}")
    
    # Decide storage location & Firestore metadata
    if req.upload_type in ["shared_knowledge", "shared_prompts"]:
        bucket_name = SHARED_BUCKET
        user_prefix = req.upload_type  # e.g., "shared_knowledge" or "shared_prompts"
        # Only admins should use these in practice; enforce in your auth later!
        blob_path = f"{user_prefix}/{uuid.uuid4()}_{req.filename}"
    elif req.upload_type in ["user_document", "user_prompt"]:
        if not req.user_id:
            raise HTTPException(status_code=400, detail="user_id required for user uploads.")
        bucket_name = USER_BUCKET
        prefix = "user_uploads" if req.upload_type == "user_document" else "user_prompts"
        blob_path = f"{prefix}/{req.user_id}/{uuid.uuid4()}_{req.filename}"
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid upload_type. Must be one of: shared_knowledge, shared_prompts, user_document, user_prompt"
        )

    try:
        # Generate signed URL
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        url = blob.generate_signed_url(
            version="v4",
            expiration=600,
            method="PUT",
            content_type=req.content_type,
        )

        # Store metadata in Firestore
        upload_id = str(uuid.uuid4())
        doc_ref = firestore_client.collection("uploads").document(upload_id)
        doc_ref.set({
            "upload_id": upload_id,
            "upload_type": req.upload_type,
            "user_id": req.user_id,
            "filename": req.filename,
            "bucket": bucket_name,
            "blob_path": blob_path,
            "content_type": req.content_type,
            "upload_url_created": firestore.SERVER_TIMESTAMP,
            "status": "pending"
        })

        logger.info(f"Generated upload URL for {upload_id}")
        return {
            "upload_url": url, 
            "upload_id": upload_id, 
            "bucket": bucket_name, 
            "blob_path": blob_path
        }
    
    except Exception as e:
        logger.error(f"Error generating upload URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@app.post("/confirm-upload")
def confirm_upload(req: ConfirmUploadRequest):
    logger.info(f"Confirming upload: {req.upload_id}")
    
    try:
        doc_ref = firestore_client.collection("uploads").document(req.upload_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Upload ID not found")
        
        doc_ref.update({
            "status": req.status,
            "upload_confirmed_at": firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"Upload confirmed: {req.upload_id}")
        return {"message": "Upload confirmed.", "upload_id": req.upload_id, "status": req.status}
    
    except Exception as e:
        logger.error(f"Error confirming upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to confirm upload: {str(e)}")

@app.get("/uploads/{upload_id}")
def get_upload_status(upload_id: str):
    """Get the status of an upload"""
    try:
        doc_ref = firestore_client.collection("uploads").document(upload_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Upload ID not found")
        
        return doc.to_dict()
    
    except Exception as e:
        logger.error(f"Error getting upload status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get upload status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable from Cloud Run
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)