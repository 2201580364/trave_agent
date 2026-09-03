"""Official-source adapters for China holiday calendar synchronization."""

from .ai_extractor import AiHolidayAnnouncementExtractor, StructuredHolidayModel
from .gov_cn import GovCnAnnouncementDiscoverer, GovCnAnnouncementFetcher
from .openai_compatible import (
    HolidaySyncSettings,
    OpenAiCompatibleStructuredHolidayModel,
)

__all__ = [
    "AiHolidayAnnouncementExtractor",
    "GovCnAnnouncementDiscoverer",
    "GovCnAnnouncementFetcher",
    "HolidaySyncSettings",
    "OpenAiCompatibleStructuredHolidayModel",
    "StructuredHolidayModel",
]
