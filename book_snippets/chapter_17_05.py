# from 08-part-7-real-systems\chapter-17-production-readiness.md:90
from agent_framework.security import PRINCIPAL_METADATA_KEY, SecureAgentConfig

@tool(description="Read the authenticated user's profile.",
      additional_properties={"source_integrity": "trusted",
                             "confidentiality": "user_identity",
                             PRINCIPAL_METADATA_KEY: authenticated_principals})
async def read_my_profile() -> str: ...

@tool(description="Send a note to another user's account.",
      additional_properties={"max_allowed_confidentiality": "user_identity",
                             PRINCIPAL_METADATA_KEY: other_principals})
async def send_to_other_account(note: str): ...
