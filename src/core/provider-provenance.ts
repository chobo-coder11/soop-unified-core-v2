import type{ProviderName,ProviderProvenance}from'../types.js';
export const PROVIDER_PROVENANCE:Record<ProviderName,ProviderProvenance>={
 native:{implementation:'native',transport:'http',upstreamFamily:'soop-official-http',independenceGroup:'native-http'},
 reindeer:{implementation:'reindeer',transport:'http',upstreamFamily:'soop-official-http',independenceGroup:'reindeer-http'},
 soopapi:{implementation:'soopapi',transport:'sidecar',upstreamFamily:'soop-official-http',independenceGroup:'soopapi-java'},
 soop4j:{implementation:'soop4j',transport:'sidecar',upstreamFamily:'soop-official-http',independenceGroup:'soop4j-java'},
 soopjs:{implementation:'soopjs',transport:'browser',upstreamFamily:'soop-public-web',independenceGroup:'soopjs-browser'}
};
