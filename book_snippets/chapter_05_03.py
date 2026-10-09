# from 03-part-2-core-architecture\chapter-05-middleware.md:67
from agent_framework.security import ContentLabel, IntegrityLabel, ConfidentialityLabel

label = ContentLabel(
    integrity=IntegrityLabel.TRUSTED,
    confidentiality=ConfidentialityLabel.PRIVATE,
    metadata={"user_id": "user-123"},
)
