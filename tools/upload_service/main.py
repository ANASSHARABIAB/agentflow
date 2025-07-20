import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage, firestore

# Configure your buckets

USER_BUCKET = os.environ["USER_BUCKET"]
SHARED_BUCKET = os.environ["SHARED_BUCKET"]


# Use service account key for both clients
sa_key_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
storage_client = storage.Client.from_service_account_json(sa_key_path)
firestore_client = firestore.Client.from_service_account_json(sa_key_path)

app = FastAPI()
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

@app.post("/upload-url")
def generate_upload_url(req: UploadUrlRequest):
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
        raise HTTPException(status_code=400, detail="Invalid upload_type.")

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
        "upload_url_created": firestore.SERVER_TIMESTAMP,
        "status": "pending"
    })

    return {"upload_url": url, "upload_id": upload_id, "bucket": bucket_name, "blob_path": blob_path}

@app.post("/confirm-upload")
def confirm_upload(upload_id: str):
    doc_ref = firestore_client.collection("uploads").document(upload_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Upload ID not found")
    doc_ref.update({
        "status": "uploaded",
        "upload_confirmed_at": firestore.SERVER_TIMESTAMP
    })
    return {"message": "Upload confirmed."}
