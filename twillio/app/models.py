from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Address(StrictModel):
    house_number: str | None = None
    street: str | None = None
    unit: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    postal_code: str | None = None
    telephone_area_code: str | None = None
    landmark: str | None = None
    location_detail: str | None = None
    unavailable_fields: list[Literal['house_number', 'street', 'unit', 'city', 'region',
                                    'country', 'postal_code', 'landmark']] = Field(default_factory=list)


class Evidence(StrictModel):
    field: str
    message_sid: str
    quote: str


class Situation(StrictModel):
    summary: str
    reporter_relationship: Literal['self', 'third_party', 'unknown'] = 'unknown'
    people_count: int | None = Field(default=None, ge=0)
    address: Address = Field(default_factory=Address)
    reported_hazards: list[str] = Field(default_factory=list)
    assistance_needs: list[str] = Field(default_factory=list)
    event_time_text: str | None = None
    reported_resolution: bool = False
    evidence: list[Evidence] = Field(default_factory=list)


class Extraction(StrictModel):
    report_type: Literal['rescue_request', 'update', 'other']
    # Full current conversation snapshot. Multiple locations remain separate situations.
    situations: list[Situation] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class IncidentPatch(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    verification_status: Literal['unverified', 'corroborated', 'responder_verified', 'disputed'] | None = None
    response_status: Literal['new', 'assessing', 'assigned', 'responding', 'resolved'] | None = None
    operational_priority: Literal['unassigned', 'urgent', 'routine'] | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: Literal['approximate', 'address', 'confirmed_point'] | None = None
    location_source: str | None = Field(default=None, min_length=1)
    clear_location: bool = False

    @model_validator(mode='after')
    def valid_location(self):
        location = (self.latitude, self.longitude, self.location_precision, self.location_source)
        if any(v is not None for v in location) and not all(v is not None for v in location):
            raise ValueError('Coordinates require both axes, precision, and source')
        if self.clear_location and any(v is not None for v in location):
            raise ValueError('Cannot set and clear location together')
        return self


class GeminiReport(StrictModel):
    message_sid: str
    conversation_id: str
    received_at: float
    processing_status: Literal['pending', 'processing', 'extracted', 'failed']
    error: str | None = None
    extraction_id: str | None = None
    generated_at: float | None = None
    model: str | None = None
    prompt_version: str | None = None
    report: Extraction | None = None
