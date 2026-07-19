from dataclasses import dataclass

from roster_engine.database import get_supabase


@dataclass(frozen=True)
class DocumentVersion:
    document_type: str
    content: str
    version: int


def get_current_document(
    document_type: str,
) -> DocumentVersion:
    client = get_supabase()

    response = (
        client.table("app_documents")
        .select("document_type,content,version")
        .eq("document_type", document_type)
        .eq("is_current", True)
        .single()
        .execute()
    )

    row = response.data

    return DocumentVersion(
        document_type=row["document_type"],
        content=row["content"],
        version=row["version"],
    )


def save_document(
    document_type: str,
    content: str,
    created_by: str | None = None,
) -> DocumentVersion:
    client = get_supabase()

    current = get_current_document(document_type)
    next_version = current.version + 1

    client.table("app_documents").update(
        {"is_current": False}
    ).eq(
        "document_type", document_type
    ).eq(
        "is_current", True
    ).execute()

    response = (
        client.table("app_documents")
        .insert(
            {
                "document_type": document_type,
                "content": content,
                "version": next_version,
                "created_by": created_by,
                "is_current": True,
            }
        )
        .execute()
    )

    row = response.data[0]

    return DocumentVersion(
        document_type=row["document_type"],
        content=row["content"],
        version=row["version"],
    )