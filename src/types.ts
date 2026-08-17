export type ProviderName='native'|'reindeer'|'soopapi'|'soop4j'|'soopjs';
export type ProviderState='healthy'|'degraded'|'open'|'half-open'|'disabled';
export type ProviderTransport='http'|'websocket'|'sidecar'|'browser';

export interface ProviderProvenance {
  implementation:ProviderName;
  transport:ProviderTransport;
  upstreamFamily:string;
  independenceGroup:string;
}

export interface ProviderHealth {
  name:ProviderName;
  state:ProviderState;
  enabled:boolean;
  successes:number;
  failures:number;
  consecutiveFailures:number;
  latencyMs?:number;
  lastSuccessAt?:string;
  lastFailureAt?:string;
  openUntil?:string;
  lastError?:string;
  openCount?:number;
  currentCooldownMs?:number;
  halfOpenTrialInFlight?:boolean;
  dynamicWeight?:number;
  successRate?:number;
  disagreementRate?:number;
  ewmaLatencyMs?:number;
}

export interface LiveSnapshot {
  streamerId:string;
  online:boolean;
  bno?:string;
  chatNo?:string;
  streamerNickname?:string;
  title?:string;
  category?:string;
  viewerCount?:number;
  startedSecondsAgo?:number;
  passwordProtected?:boolean;
  resolution?:string;
  bitrate?:number;
  thumbnailUrl?:string;
  channelDomain?:string;
  channelPort?:number;
  ftk?:string;
  geoCountryCode?:string;
  geoRegionCode?:string;
  acceptLanguage?:string;
  serviceLanguage?:string;
  raw?:unknown;
}

export interface ChannelSnapshot {
  streamerId:string;
  nickname?:string;
  stationName?:string;
  stationTitle?:string;
  profileImage?:string;
  favorites?:number;
  subscribers?:number;
  totalViewCount?:number;
  currentViewerCount?:number;
  broadNo?:number;
  broadTitle?:string;
  isPassword?:boolean;
  explanation?:string;
  raw?:unknown;
}

export interface ProviderObservation<T> {
  provider:ProviderName;
  ok:boolean;
  latencyMs:number;
  observedAt:string;
  value?:T;
  error?:string;
  provenance?:ProviderProvenance;
  stale?:boolean;
}

export type ConsensusStatus='confirmed'|'uncertain'|'single-source';
export type OnlineState='online'|'offline'|'uncertain';
export interface FieldConsensusMeta {
  value?:unknown;
  agreement:number;
  sourceCount:number;
  sources:ProviderName[];
  conflictingProviders?:ProviderName[];
}

export interface FreshnessMeta {
  state:'fresh'|'stale';
  ageMs:number;
  staleReason?:string;
}

export interface ConsensusMeta {
  status:ConsensusStatus;
  onlineState?:OnlineState;
  agreement:number;
  totalWeight:number;
  winningWeight:number;
  sourceCount:number;
  implementationGroups:number;
  upstreamFamilies:number;
  reason?:string;
  outlierProviders?:ProviderName[];
  fields?:Record<string,FieldConsensusMeta>;
}

export interface UnifiedResult<T> {
  data:T;
  confidence:number;
  source:ProviderName;
  corroboratedBy:ProviderName[];
  observations:ProviderObservation<T>[];
  observedAt:string;
  consensus:ConsensusMeta;
  freshness?:FreshnessMeta;
}

export type EventCategory='connection'|'chat'|'viewer'|'donation'|'moderation'|'item'|'notification'|'system'|'unknown';
export type EventSupportLevel='stable'|'conditional'|'raw-only';
export interface EventDescriptor {code:number;name:string;description:string;category:EventCategory;supportLevel:EventSupportLevel;note?:string}

export interface CanonicalEvent {
  id:string;
  streamerId:string;
  code:number;
  type:string;
  description:string;
  category:EventCategory;
  supportLevel:EventSupportLevel;
  source:ProviderName;
  receivedAt:string;
  providerEventId?:string;
  user?:{id?:string;nickname?:string;flags?:string;subscriptionMonth?:string};
  target?:{id?:string;nickname?:string};
  message?:string;
  donation?:{kind:string;amount?:number;fanOrder?:number;itemCode?:string;extra?:unknown};
  moderation?:{action:string;reason?:string;durationSeconds?:number;adminId?:string};
  payload:Record<string,unknown>;
  raw?:string;
  fingerprint?:string;
}

export interface RawPacketRecord {streamerId:string;code:number;type:string;receivedAt:string;raw:string;signature:string}

export type ProtocolAnomalyKind='parse-error'|'length-mismatch'|'unknown-code'|'liveness-timeout'|'join-timeout';
export interface ProtocolAnomaly {
  kind:ProtocolAnomalyKind;
  streamerId:string;
  receivedAt:string;
  source:ProviderName;
  code?:number;
  signature?:string;
  detail?:string;
  raw?:string;
}

export interface ProtocolDriftIncident {
  id:string;
  startedAt:string;
  detectedAt:string;
  severity:'medium'|'high';
  reason:'unknown-rate'|'malformed-rate';
  windowMs:number;
  totalEvents:number;
  unknownEvents:number;
  malformedPackets:number;
  affectedStreams:number;
  unknownRatio:number;
  sampleCodes:number[];
  sampleSignatures:string[];
  sampleStreams:string[];
}

export interface ProtocolIncidentBundle {
  incident:ProtocolDriftIncident;
  capturedAt:string;
  packets:RawPacketRecord[];
  anomalies:ProtocolAnomaly[];
}
