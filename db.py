import streamlit as st
from supabase import create_client, Client
import mimetypes

# Singleton to avoid reconnecting on every rerun
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def get_templates():
    """Fetch all templates ordered by creation date."""
    supabase = init_supabase()
    try:
        response = supabase.table("templates").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Supabase: {e}")
        return []

def create_template(name, company_name, company_address, primary_color, logo_url=None):
    """Insert a new template."""
    supabase = init_supabase()
    data = {
        "name": name,
        "company_name": company_name,
        "company_address": company_address,
        "primary_color": primary_color,
        "logo_url": logo_url
    }
    try:
        response = supabase.table("templates").insert(data).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Création: {e}")
        return None

def update_template(template_id, name, company_name, company_address, primary_color, logo_url=None):
    """Update an existing template."""
    supabase = init_supabase()
    data = {
        "name": name,
        "company_name": company_name,
        "company_address": company_address,
        "primary_color": primary_color,
        "logo_url": logo_url
    }
    try:
        response = supabase.table("templates").update(data).eq("id", template_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Mise à jour: {e}")
        return None

def delete_template(template_id):
    """Delete a template by ID."""
    supabase = init_supabase()
    try:
        response = supabase.table("templates").delete().eq("id", template_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Suppression: {e}")
        return None

def upload_logo(file_obj, file_name):
    """Uploads a file to 'logos' bucket and returns Public URL."""
    supabase = init_supabase()
    bucket_name = "logos"
    
    # Clean filename or use unique ID if needed (for now, use original)
    # Ideally should imply uuid to avoid collision
    import uuid
    ext = file_name.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    
    try:
        file_bytes = file_obj.getvalue()
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        
        supabase.storage.from_(bucket_name).upload(
            path=unique_name,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "false"}
        )
        
        # Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(unique_name)
        return public_url
    except Exception as e:
        st.error(f"Erreur Upload: {e}")
        return None


# ================================================================
# EMAIL TEMPLATES CRUD
# ================================================================

def get_email_templates():
    """Fetch all email templates ordered by creation date."""
    supabase = init_supabase()
    try:
        response = supabase.table("email_templates").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Supabase (email_templates): {e}")
        return []

def create_email_template(name, subject, body):
    """Insert a new email template."""
    supabase = init_supabase()
    data = {"name": name, "subject": subject, "body": body}
    try:
        response = supabase.table("email_templates").insert(data).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Création email template: {e}")
        return None

def update_email_template(template_id, name, subject, body):
    """Update an existing email template."""
    supabase = init_supabase()
    data = {"name": name, "subject": subject, "body": body}
    try:
        response = supabase.table("email_templates").update(data).eq("id", template_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Mise à jour email template: {e}")
        return None

def delete_email_template(template_id):
    """Delete an email template by ID."""
    supabase = init_supabase()
    try:
        response = supabase.table("email_templates").delete().eq("id", template_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Suppression email template: {e}")
        return None

def update_template_emails(template_id, emails):
    """Update the emails list on a visual template."""
    supabase = init_supabase()
    try:
        response = supabase.table("templates").update({"emails": emails}).eq("id", template_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Erreur Mise à jour emails: {e}")
        return None
