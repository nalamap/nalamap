```mermaid
erDiagram
  %% ===================== Entities =====================
  Users {
    uuid id PK
    text name
    text email "unique"
    text password
  }

  Stac_item {
    uuid id PK
    text type
    text stac_version
    jsonb stac_extensions
    geometry geometry
    geometry bbox
    jsonb properties
    jsonb links
    jsonb assets
    text collection "FK -> Stac_Collection.id"
    vector embeddings
  }

  Stac_Collection {
    text id PK
    text catalog "FK -> Stac_Catalog.id"
    text type
    text stac_version
    jsonb stac_extensions
    text title
    text description
    text[] keywords
    text license
    jsonb providers
    jsonb extent
    jsonb summaries
    jsonb links
    jsonb assets
    jsonb item_assets
  }

  Stac_Catalog {
    text id PK
    text type
    text stac_version
    jsonb stac_extensions
    text title
    text description
    jsonb links
  }

  Layers {
    uuid id PK
    text data_link
    text data_type
    text name
    text description
    bool derived
    jsonb style
  }

  Maps {
    uuid id PK
    text name
    text description
    jsonb layers "ordered refs or metadata"
  }

  Projects {
    uuid id PK
    uuid owner_id "FK -> Users.id"
    text name
    text description
  }

  Chat_sessions {
    uuid id PK
    uuid owner_id "FK -> Users.id"
    uuid project_id "unique nullable"
    uuid map_id "unique nullable"
    text title
    timestamptz created_at
  }

  chat_messages {
    uuid id PK
    uuid session_id "FK -> Chat_sessions.id"
    text role "user|assistant|system|tool"
    text content
    jsonb metadata
    timestamptz created_at
  }

  External_Services {
    uuid id PK
    uuid owner_id "FK -> Users.id"
    text name
    text service_type "geoserver|arcgis|wms|wfs|wmts|wcs|xyz|pmtiles"
    text base_url
    text auth_kind "none|token|basic|oauth2"
    jsonb auth_payload
    timestamptz created_at
  }

  Styles {
    uuid id PK
    uuid item_id "FK -> Stac_item.id"
    text name
    text format "mapbox|geostyler|sld"
    jsonb style_json
    uuid created_by "FK -> Users.id"
    timestamptz created_at
    timestamptz updated_at
  }

  External_Layers {
    uuid id PK
    uuid service_id "FK -> External_Services.id"
    text remote_name
    jsonb capabilities
  }

  %% ===================== Join / ACL tables =====================
  Project_Shares {
    uuid user_id "FK -> Users.id"
    uuid project_id "FK -> Projects.id"
    text role "owner|editor|viewer"
    uuid project_share_id "PK -> (user_id, project_id)"
  }

  Map_Shares {
    uuid user_id "FK -> Users.id"
    uuid map_id "FK -> Maps.id"
    text role "owner|editor|viewer"
    uuid map_share_id "PK -> (user_id, map_id)"
  }

  Chat_Session_Shares {
    uuid user_id "FK -> Users.id"
    uuid session_id "FK -> Chat_sessions.id"
    text role "owner|editor|viewer"
    uuid chat_share_id "PK -> (user_id, session_id)"
  }

  User_External_Services {
    uuid user_id "FK -> Users.id"
    uuid service_id "FK -> External_Services.id"
    uuid user_external_service_id "PK -> (user_id, service_id)"
  }

  User_Stac_Collections {
    uuid user_id "FK -> Users.id"
    text collection_id "FK -> Stac_Collection.id"
    uuid user_stac_coll_id "PK -> (user_id, collection_id)"
  }

  User_Stac_Catalog {
    uuid user_id "FK -> Users.id"
    text catalog_id "FK -> Stac_Catalog.id"
    uuid user_stac_cata_id "PK -> (user_id, catalog_id)"
  }

  Map_Layers {
    uuid map_id "FK -> Maps.id"
    uuid layer_id "FK -> Layers.id"
    int z_index
    bool visible
    uuid map_layers_id "PK -> (map_id, layer_id)"
  }

  %% ===================== Relationships =====================

  %% Catalog & Collections & Items
  Stac_Collection ||--o{ Stac_item : "has items"
  %% External service registered as its own STAC catalog
  External_Services ||--|| Stac_Catalog : "is a"

  %% Styles
  Users ||--o{ Styles : "created_by"

  %% Layers <-> Maps (M:N)
  Maps ||--o{ Map_Layers : "composition"
  Layers ||--o{ Map_Layers : "used in"

  %% Projects 1:1 Maps & 1:1 Chat_sessions
  Projects ||--|| Maps : "one map per project"
  Projects ||--|| Chat_sessions : "one chat per project"
  %% (Chat_sessions also may reference map_id uniquely)

  %% Messages
  Chat_sessions ||--o{ chat_messages : "has"

  %% Sharing (M:N)
  Users ||--o{ Project_Shares : ""
  Projects ||--o{ Project_Shares : "shared with"

  Users ||--o{ Map_Shares : ""
  Maps ||--o{ Map_Shares : "shared with"

  Users ||--o{ Chat_Session_Shares : ""
  Chat_sessions ||--o{ Chat_Session_Shares : "shared with"

  Users ||--o{ User_External_Services : ""
  External_Services ||--o{ User_External_Services : "access to"

  Users ||--o{ User_Stac_Collections : ""
  Stac_Collection ||--o{ User_Stac_Collections : "searchable for"
