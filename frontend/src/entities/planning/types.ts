export interface AnonymousSession {
  principal_id: string
  access_token: string
  expires_at: string
}

export interface Attraction {
  attraction_id: string
  name: string
  suggested_duration_min: number
  is_always_open: boolean
  is_indoor: boolean
  energy_level: number
  close_days: number[]
  coordinate: { lat: number; lng: number } | null
}

export interface Draft {
  draft_id: string
  draft_version: number
  status: string
  city: { city_id: string; name: string; timezone: string }
  travel_facts: TravelFactsResponse | null
  selected_attraction_ids: string[]
  visit_period_preferences: unknown[]
  last_saved_at: string
}

export interface TravelFactsResponse {
  start_date: string
  end_date: string
  arrival: {
    transport_type: string
    confirmation: string
    arrives_at: string
    station_to_city_min: number
  }
  departure: {
    transport_type: string
    confirmation: string
    departs_at: string
    station_early_min: number
    last_visit_to_station_min: number
  }
  travel_mode: string
  crowd_type: string
}

export interface GenerationIntent {
  generation_intent_id: string
  status: string
  trip_id: string | null
  trip_revision_id: string | null
  failure_code: string | null
  replacement_draft_id?: string
  replacement_draft_version?: number
}

export interface TripRevision {
  trip_revision_id: string
  trip_id: string
  revision_number: number
  completion_kind: 'complete_success' | 'partial_success'
  has_soft_degradation: boolean
  result_snapshot: TripResult
}

export interface TripSummary {
  trip_id: string
  city_id: string
  city_name: string
  current_revision_id: string
  current_revision_number: number
  completion_kind: 'complete_success' | 'partial_success'
  has_soft_degradation: boolean
  start_date: string | null
  end_date: string | null
  scheduled_count: number
  unplaced_count: number
  updated_at: string
  revision_count: number
}

export interface TripListResponse {
  items: TripSummary[]
  limit: number
  offset: number
  has_more: boolean
}

export interface TripRevisionSummary {
  trip_revision_id: string
  revision_number: number
  is_current: boolean
  completion_kind: 'complete_success' | 'partial_success'
  has_soft_degradation: boolean
  start_date: string | null
  end_date: string | null
  scheduled_count: number
  unplaced_count: number
  created_at: string
}

export interface TripRevisionListResponse {
  trip_id: string
  current_revision_id: string
  items: TripRevisionSummary[]
}

export interface TripResult {
  schema_version: string
  summary?: Record<string, number>
  days: Array<{
    date: string
    search_status?: string
    total_travel_min?: number
    weather?: { condition?: string; basis?: string }
    nodes: Array<{
      node_id: string
      attraction_id: string
      name: string
      arrival_min: number
      leave_min: number
      planned_duration_min: number
      travel_from_previous_min?: number
      buffered_travel_from_previous_min?: number
      travel_basis?: 'approximate' | 'gaode' | null
      travel_distance_m?: number | null
      travel_fallback_reason?: string | null
      transport_mode?: 'walking' | 'transit' | 'driving' | 'walking_estimate' | 'taxi_estimate' | 'transit_or_taxi_estimate' | null
      timing_kind?: 'flexible' | 'fixed_event'
    }>
    lunch?: MealBreak | null
    meal?: MealBreak | null
  }>
  unplaced?: Array<{ attraction_id: string; name: string; reason_code: string }>
  degradations?: Array<{ code: string; message: string; count: number }>
  provenance?: Record<string, unknown>
}

export interface MealBreak {
  status?: 'full' | 'reduced' | 'unscheduled'
  start_min?: number | null
  end_min?: number | null
  duration_min?: number
  notice?: string
}
