/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NEXUS_DATA_SOURCE?: 'live' | 'demo';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
