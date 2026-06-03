import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger("DnDAssistant.GoogleDocs")


def append_to_google_doc(credentials_info: dict, document_id: str, text: str) -> bool:
    """
    Appends text to a Google Document using Google Service Account credentials.
    """
    try:
        scopes = ["https://www.googleapis.com/auth/documents"]
        creds = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=scopes
        )
        service = build("docs", "v1", credentials=creds)

        # Retrieve document to get length / end index
        doc = service.documents().get(documentId=document_id).execute()

        body = doc.get("body")
        content = body.get("content", [])
        end_index = 1
        if content:
            end_index = content[-1].get("endIndex", 1)
            # Safe boundary check: index must be at least 1 and less than endIndex
            if end_index > 1:
                insert_index = end_index - 1
            else:
                insert_index = 1
        else:
            insert_index = 1

        requests = [
            {
                "insertText": {
                    "location": {
                        "index": insert_index,
                    },
                    "text": text,
                }
            }
        ]

        service.documents().batchUpdate(
            documentId=document_id, body={"requests": requests}
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to append to Google Doc: {e}", exc_info=True)
        return False
