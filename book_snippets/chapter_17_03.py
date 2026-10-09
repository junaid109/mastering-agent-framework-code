# from 08-part-7-real-systems\chapter-17-production-readiness.md:50
from agent_framework import register_checkpoint_type, FileCheckpointStorage

# Register the application-defined request type so file storage can reconstruct it
register_checkpoint_type(HumanApprovalRequest)

# Alternatively, scope permission to this storage instance:
allowed_types = [f"{HumanApprovalRequest.__module__}:{HumanApprovalRequest.__qualname__}"]
storage = FileCheckpointStorage(storage_path=TEMP_DIR, allowed_checkpoint_types=allowed_types)
