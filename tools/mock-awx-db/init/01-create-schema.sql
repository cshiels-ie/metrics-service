-- Generated AWX Schema DDL
-- Auto-generated from Schema.sql

SET CLIENT_ENCODING TO 'UTF8';
SET STANDARD_CONFORMING_STRINGS TO ON;

-- Table: auth_group
CREATE TABLE IF NOT EXISTS auth_group (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

-- Table: auth_group_permissions
CREATE TABLE IF NOT EXISTS auth_group_permissions (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL
);

-- Table: auth_permission
CREATE TABLE IF NOT EXISTS auth_permission (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    content_type_id INTEGER NOT NULL,
    codename VARCHAR(255) NOT NULL
);

-- Table: auth_user
CREATE TABLE IF NOT EXISTS auth_user (
    id SERIAL PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    last_login TIMESTAMPTZ,
    is_superuser BOOLEAN NOT NULL,
    username VARCHAR(255) NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_staff BOOLEAN NOT NULL,
    is_active BOOLEAN NOT NULL,
    date_joined TIMESTAMPTZ NOT NULL
);

-- Table: auth_user_groups
CREATE TABLE IF NOT EXISTS auth_user_groups (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL
);

-- Table: auth_user_user_permissions
CREATE TABLE IF NOT EXISTS auth_user_user_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL
);

-- Table: conf_setting
CREATE TABLE IF NOT EXISTS conf_setting (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB,
    user_id INTEGER
);

-- Table: dab_rbac_dabpermission
CREATE TABLE IF NOT EXISTS dab_rbac_dabpermission (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    codename VARCHAR(255) NOT NULL,
    content_type_id INTEGER NOT NULL
);

-- Table: dab_rbac_objectrole
CREATE TABLE IF NOT EXISTS dab_rbac_objectrole (
    id BIGSERIAL PRIMARY KEY,
    object_id TEXT NOT NULL,
    content_type_id INTEGER NOT NULL,
    role_definition_id BIGINT NOT NULL
);

-- Table: dab_rbac_objectrole_provides_teams
CREATE TABLE IF NOT EXISTS dab_rbac_objectrole_provides_teams (
    id SERIAL PRIMARY KEY,
    objectrole_id BIGINT NOT NULL,
    team_id INTEGER NOT NULL
);

-- Table: dab_rbac_roledefinition
CREATE TABLE IF NOT EXISTS dab_rbac_roledefinition (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    managed BOOLEAN NOT NULL,
    content_type_id INTEGER,
    created_by_id INTEGER,
    created TIMESTAMPTZ NOT NULL,
    modified_by_id INTEGER,
    modified TIMESTAMPTZ NOT NULL
);

-- Table: dab_rbac_roledefinition_permissions
CREATE TABLE IF NOT EXISTS dab_rbac_roledefinition_permissions (
    id SERIAL PRIMARY KEY,
    roledefinition_id BIGINT NOT NULL,
    dabpermission_id BIGINT NOT NULL
);

-- Table: dab_rbac_roleevaluation
CREATE TABLE IF NOT EXISTS dab_rbac_roleevaluation (
    id BIGSERIAL PRIMARY KEY,
    codename TEXT NOT NULL,
    content_type_id INTEGER NOT NULL,
    object_id INTEGER NOT NULL,
    role_id BIGINT NOT NULL
);

-- Table: dab_rbac_roleevaluationuuid
CREATE TABLE IF NOT EXISTS dab_rbac_roleevaluationuuid (
    id BIGSERIAL PRIMARY KEY,
    codename TEXT NOT NULL,
    content_type_id INTEGER NOT NULL,
    object_id UUID NOT NULL,
    role_id BIGINT NOT NULL
);

-- Table: dab_rbac_roleteamassignment
CREATE TABLE IF NOT EXISTS dab_rbac_roleteamassignment (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    content_type_id INTEGER,
    object_id TEXT,
    role_definition_id BIGINT NOT NULL,
    created_by_id INTEGER,
    team_id INTEGER NOT NULL,
    object_role_id BIGINT
);

-- Table: dab_rbac_roleuserassignment
CREATE TABLE IF NOT EXISTS dab_rbac_roleuserassignment (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    content_type_id INTEGER,
    object_id TEXT,
    role_definition_id BIGINT NOT NULL,
    created_by_id INTEGER,
    user_id INTEGER NOT NULL,
    object_role_id BIGINT
);

-- Table: dab_resource_registry_resource
CREATE TABLE IF NOT EXISTS dab_resource_registry_resource (
    id BIGSERIAL PRIMARY KEY,
    object_id TEXT NOT NULL,
    service_id UUID NOT NULL,
    ansible_id UUID NOT NULL,
    name VARCHAR(255),
    content_type_id INTEGER NOT NULL,
    is_partially_migrated BOOLEAN NOT NULL
);

-- Table: dab_resource_registry_resourcetype
CREATE TABLE IF NOT EXISTS dab_resource_registry_resourcetype (
    id BIGSERIAL PRIMARY KEY,
    externally_managed BOOLEAN NOT NULL,
    name VARCHAR(255) NOT NULL,
    content_type_id INTEGER NOT NULL
);

-- Table: dab_resource_registry_serviceid
CREATE TABLE IF NOT EXISTS dab_resource_registry_serviceid (
    id UUID PRIMARY KEY NOT NULL
);

-- Table: django_content_type
CREATE TABLE IF NOT EXISTS django_content_type (
    id SERIAL PRIMARY KEY,
    app_label VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL
);

-- Table: django_migrations
CREATE TABLE IF NOT EXISTS django_migrations (
    id SERIAL PRIMARY KEY,
    app VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    applied TIMESTAMPTZ NOT NULL
);

-- Table: django_session
CREATE TABLE IF NOT EXISTS django_session (
    session_key VARCHAR(255) NOT NULL,
    session_data TEXT NOT NULL,
    expire_date TIMESTAMPTZ NOT NULL
);

-- Table: django_site
CREATE TABLE IF NOT EXISTS django_site (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL
);

-- Table: flags_flagstate
CREATE TABLE IF NOT EXISTS flags_flagstate (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    condition VARCHAR(255) NOT NULL,
    value VARCHAR(255) NOT NULL,
    required BOOLEAN NOT NULL
);

-- Table: main_activitystream
CREATE TABLE IF NOT EXISTS main_activitystream (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    changes TEXT NOT NULL,
    object_relationship_type TEXT NOT NULL,
    object1 TEXT NOT NULL,
    object2 TEXT NOT NULL,
    actor_id INTEGER,
    action_node VARCHAR(255) NOT NULL,
    deleted_actor JSONB,
    setting JSONB NOT NULL
);

-- Table: main_activitystream_ad_hoc_command
CREATE TABLE IF NOT EXISTS main_activitystream_ad_hoc_command (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    adhoccommand_id INTEGER NOT NULL
);

-- Table: main_activitystream_credential
CREATE TABLE IF NOT EXISTS main_activitystream_credential (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_activitystream_credential_type
CREATE TABLE IF NOT EXISTS main_activitystream_credential_type (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    credentialtype_id INTEGER NOT NULL
);

-- Table: main_activitystream_execution_environment
CREATE TABLE IF NOT EXISTS main_activitystream_execution_environment (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    executionenvironment_id INTEGER NOT NULL
);

-- Table: main_activitystream_group
CREATE TABLE IF NOT EXISTS main_activitystream_group (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL
);

-- Table: main_activitystream_host
CREATE TABLE IF NOT EXISTS main_activitystream_host (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL
);

-- Table: main_activitystream_instance
CREATE TABLE IF NOT EXISTS main_activitystream_instance (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    instance_id INTEGER NOT NULL
);

-- Table: main_activitystream_instance_group
CREATE TABLE IF NOT EXISTS main_activitystream_instance_group (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    instancegroup_id INTEGER NOT NULL
);

-- Table: main_activitystream_inventory
CREATE TABLE IF NOT EXISTS main_activitystream_inventory (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL
);

-- Table: main_activitystream_inventory_source
CREATE TABLE IF NOT EXISTS main_activitystream_inventory_source (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    inventorysource_id INTEGER NOT NULL
);

-- Table: main_activitystream_inventory_update
CREATE TABLE IF NOT EXISTS main_activitystream_inventory_update (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    inventoryupdate_id INTEGER NOT NULL
);

-- Table: main_activitystream_job
CREATE TABLE IF NOT EXISTS main_activitystream_job (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL
);

-- Table: main_activitystream_job_template
CREATE TABLE IF NOT EXISTS main_activitystream_job_template (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    jobtemplate_id INTEGER NOT NULL
);

-- Table: main_activitystream_label
CREATE TABLE IF NOT EXISTS main_activitystream_label (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_activitystream_notification
CREATE TABLE IF NOT EXISTS main_activitystream_notification (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    notification_id INTEGER NOT NULL
);

-- Table: main_activitystream_notification_template
CREATE TABLE IF NOT EXISTS main_activitystream_notification_template (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_activitystream_o_auth2_access_token
CREATE TABLE IF NOT EXISTS main_activitystream_o_auth2_access_token (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    oauth2accesstoken_id BIGINT NOT NULL
);

-- Table: main_activitystream_o_auth2_application
CREATE TABLE IF NOT EXISTS main_activitystream_o_auth2_application (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    oauth2application_id BIGINT NOT NULL
);

-- Table: main_activitystream_organization
CREATE TABLE IF NOT EXISTS main_activitystream_organization (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL
);

-- Table: main_activitystream_project
CREATE TABLE IF NOT EXISTS main_activitystream_project (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL
);

-- Table: main_activitystream_project_update
CREATE TABLE IF NOT EXISTS main_activitystream_project_update (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    projectupdate_id INTEGER NOT NULL
);

-- Table: main_activitystream_receptor_address
CREATE TABLE IF NOT EXISTS main_activitystream_receptor_address (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    receptoraddress_id INTEGER NOT NULL
);

-- Table: main_activitystream_role
CREATE TABLE IF NOT EXISTS main_activitystream_role (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL
);

-- Table: main_activitystream_schedule
CREATE TABLE IF NOT EXISTS main_activitystream_schedule (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL
);

-- Table: main_activitystream_team
CREATE TABLE IF NOT EXISTS main_activitystream_team (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL
);

-- Table: main_activitystream_unified_job
CREATE TABLE IF NOT EXISTS main_activitystream_unified_job (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    unifiedjob_id INTEGER NOT NULL
);

-- Table: main_activitystream_unified_job_template
CREATE TABLE IF NOT EXISTS main_activitystream_unified_job_template (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    unifiedjobtemplate_id INTEGER NOT NULL
);

-- Table: main_activitystream_user
CREATE TABLE IF NOT EXISTS main_activitystream_user (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_approval
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_approval (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowapproval_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_approval_template
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_approval_template (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowapprovaltemplate_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_job
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_job (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowjob_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_job_node
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_job_node (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_job_template
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_job_template (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowjobtemplate_id INTEGER NOT NULL
);

-- Table: main_activitystream_workflow_job_template_node
CREATE TABLE IF NOT EXISTS main_activitystream_workflow_job_template_node (
    id SERIAL PRIMARY KEY,
    activitystream_id INTEGER NOT NULL,
    workflowjobtemplatenode_id INTEGER NOT NULL
);

-- Table: main_adhoccommand
CREATE TABLE IF NOT EXISTS main_adhoccommand (
    unifiedjob_ptr_id INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL,
    "limit" TEXT NOT NULL,
    module_name VARCHAR(255) NOT NULL,
    module_args TEXT NOT NULL,
    forks INTEGER NOT NULL,
    verbosity INTEGER NOT NULL,
    become_enabled BOOLEAN NOT NULL,
    credential_id INTEGER,
    inventory_id INTEGER,
    extra_vars TEXT NOT NULL,
    diff_mode BOOLEAN NOT NULL
);

-- Table: main_adhoccommandevent
CREATE TABLE IF NOT EXISTS main_adhoccommandevent (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    ad_hoc_command_id INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_credential
CREATE TABLE IF NOT EXISTS main_credential (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER,
    admin_role_id INTEGER,
    use_role_id INTEGER,
    read_role_id INTEGER,
    inputs JSONB NOT NULL,
    credential_type_id INTEGER NOT NULL,
    managed BOOLEAN NOT NULL
);

-- Table: main_credentialinputsource
CREATE TABLE IF NOT EXISTS main_credentialinputsource (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    input_field_name VARCHAR(255) NOT NULL,
    metadata JSONB NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    source_credential_id INTEGER,
    target_credential_id INTEGER
);

-- Table: main_credentialtype
CREATE TABLE IF NOT EXISTS main_credentialtype (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    kind VARCHAR(255) NOT NULL,
    managed BOOLEAN NOT NULL,
    inputs JSONB NOT NULL,
    injectors JSONB NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    namespace VARCHAR(255)
);

-- Table: main_custominventoryscript
CREATE TABLE IF NOT EXISTS main_custominventoryscript (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    script TEXT NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER
);

-- Table: main_eventquery
CREATE TABLE IF NOT EXISTS main_eventquery (
    id SERIAL PRIMARY KEY,
    fqcn VARCHAR(255) NOT NULL,
    collection_version VARCHAR(255) NOT NULL,
    event_query JSONB NOT NULL
);

-- Table: main_executionenvironment
CREATE TABLE IF NOT EXISTS main_executionenvironment (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    image VARCHAR(255) NOT NULL,
    managed BOOLEAN NOT NULL,
    created_by_id INTEGER,
    credential_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER,
    name VARCHAR(255) NOT NULL,
    pull VARCHAR(255) NOT NULL
);

-- Table: main_group
CREATE TABLE IF NOT EXISTS main_group (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    variables TEXT NOT NULL,
    created_by_id INTEGER,
    inventory_id INTEGER NOT NULL,
    modified_by_id INTEGER
);

-- Table: main_group_hosts
CREATE TABLE IF NOT EXISTS main_group_hosts (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL
);

-- Table: main_group_inventory_sources
CREATE TABLE IF NOT EXISTS main_group_inventory_sources (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    inventorysource_id INTEGER NOT NULL
);

-- Table: main_group_parents
CREATE TABLE IF NOT EXISTS main_group_parents (
    id SERIAL PRIMARY KEY,
    from_group_id INTEGER NOT NULL,
    to_group_id INTEGER NOT NULL
);

-- Table: main_host
CREATE TABLE IF NOT EXISTS main_host (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL,
    instance_id VARCHAR(255) NOT NULL,
    variables TEXT NOT NULL,
    created_by_id INTEGER,
    inventory_id INTEGER NOT NULL,
    last_job_host_summary_id INTEGER,
    modified_by_id INTEGER,
    last_job_id INTEGER,
    ansible_facts JSONB NOT NULL,
    ansible_facts_modified TIMESTAMPTZ
);

-- Table: main_host_inventory_sources
CREATE TABLE IF NOT EXISTS main_host_inventory_sources (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL,
    inventorysource_id INTEGER NOT NULL
);

-- Table: main_hostmetric
CREATE TABLE IF NOT EXISTS main_hostmetric (
    hostname VARCHAR(255) NOT NULL,
    first_automation TIMESTAMPTZ NOT NULL,
    last_automation TIMESTAMPTZ NOT NULL,
    last_deleted TIMESTAMPTZ,
    automated_counter BIGINT NOT NULL,
    deleted_counter INTEGER NOT NULL,
    deleted BOOLEAN NOT NULL,
    used_in_inventories INTEGER,
    id SERIAL PRIMARY KEY
);

-- Table: main_hostmetricsummarymonthly
CREATE TABLE IF NOT EXISTS main_hostmetricsummarymonthly (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    license_consumed BIGINT NOT NULL,
    license_capacity BIGINT NOT NULL,
    hosts_added INTEGER NOT NULL,
    hosts_deleted INTEGER NOT NULL,
    indirectly_managed_hosts INTEGER NOT NULL
);

-- Table: main_indirectmanagednodeaudit
CREATE TABLE IF NOT EXISTS main_indirectmanagednodeaudit (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    name VARCHAR(255) NOT NULL,
    canonical_facts JSONB NOT NULL,
    facts JSONB NOT NULL,
    events JSONB NOT NULL,
    count INTEGER NOT NULL,
    host_id INTEGER,
    inventory_id INTEGER,
    job_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL
);

-- Table: main_instance
CREATE TABLE IF NOT EXISTS main_instance (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(255) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    capacity INTEGER NOT NULL,
    version VARCHAR(255) NOT NULL,
    capacity_adjustment NUMERIC NOT NULL,
    cpu NUMERIC NOT NULL,
    memory BIGINT NOT NULL,
    cpu_capacity INTEGER NOT NULL,
    mem_capacity INTEGER NOT NULL,
    enabled BOOLEAN NOT NULL,
    managed_by_policy BOOLEAN NOT NULL,
    ip_address VARCHAR(255) NOT NULL,
    node_type VARCHAR(255) NOT NULL,
    last_seen TIMESTAMPTZ,
    errors TEXT NOT NULL,
    last_health_check TIMESTAMPTZ,
    node_state VARCHAR(255) NOT NULL,
    health_check_started TIMESTAMPTZ,
    managed BOOLEAN NOT NULL
);

-- Table: main_instancegroup
CREATE TABLE IF NOT EXISTS main_instancegroup (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    policy_instance_list JSONB NOT NULL,
    policy_instance_minimum INTEGER NOT NULL,
    policy_instance_percentage INTEGER NOT NULL,
    credential_id INTEGER,
    pod_spec_override TEXT NOT NULL,
    is_container_group BOOLEAN NOT NULL,
    max_concurrent_jobs INTEGER NOT NULL,
    max_forks INTEGER NOT NULL,
    admin_role_id INTEGER,
    read_role_id INTEGER,
    use_role_id INTEGER
);

-- Table: main_instancegroup_instances
CREATE TABLE IF NOT EXISTS main_instancegroup_instances (
    id SERIAL PRIMARY KEY,
    instancegroup_id INTEGER NOT NULL,
    instance_id INTEGER NOT NULL
);

-- Table: main_instancelink
CREATE TABLE IF NOT EXISTS main_instancelink (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    link_state VARCHAR(255) NOT NULL,
    target_id INTEGER NOT NULL
);

-- Table: main_inventory
CREATE TABLE IF NOT EXISTS main_inventory (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    variables TEXT NOT NULL,
    has_active_failures BOOLEAN NOT NULL,
    total_hosts INTEGER NOT NULL,
    hosts_with_active_failures INTEGER NOT NULL,
    total_groups INTEGER NOT NULL,
    has_inventory_sources BOOLEAN NOT NULL,
    total_inventory_sources INTEGER NOT NULL,
    inventory_sources_with_failures INTEGER NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER,
    admin_role_id INTEGER,
    adhoc_role_id INTEGER,
    update_role_id INTEGER,
    use_role_id INTEGER,
    read_role_id INTEGER,
    host_filter TEXT,
    kind VARCHAR(255) NOT NULL,
    pending_deletion BOOLEAN NOT NULL,
    prevent_instance_group_fallback BOOLEAN NOT NULL,
    opa_query_path VARCHAR(255)
);

-- Table: main_inventory_labels
CREATE TABLE IF NOT EXISTS main_inventory_labels (
    id SERIAL PRIMARY KEY,
    inventory_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_inventoryconstructedinventorymembership
CREATE TABLE IF NOT EXISTS main_inventoryconstructedinventorymembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    constructed_inventory_id INTEGER NOT NULL,
    input_inventory_id INTEGER NOT NULL
);

-- Table: main_inventorygroupvariableswithhistory
CREATE TABLE IF NOT EXISTS main_inventorygroupvariableswithhistory (
    id SERIAL PRIMARY KEY,
    variables JSONB NOT NULL,
    group_id INTEGER,
    inventory_id INTEGER
);

-- Table: main_inventoryinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_inventoryinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL
);

-- Table: main_inventorysource
CREATE TABLE IF NOT EXISTS main_inventorysource (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    source VARCHAR(255) NOT NULL,
    source_path VARCHAR(255) NOT NULL,
    source_vars TEXT NOT NULL,
    overwrite BOOLEAN NOT NULL,
    overwrite_vars BOOLEAN NOT NULL,
    update_on_launch BOOLEAN NOT NULL,
    update_cache_timeout INTEGER NOT NULL,
    inventory_id INTEGER,
    timeout INTEGER NOT NULL,
    source_project_id INTEGER,
    verbosity INTEGER NOT NULL,
    custom_virtualenv VARCHAR(255),
    enabled_value TEXT NOT NULL,
    enabled_var TEXT NOT NULL,
    host_filter TEXT NOT NULL,
    scm_branch VARCHAR(255) NOT NULL,
    "limit" TEXT NOT NULL
);

-- Table: main_inventoryupdate
CREATE TABLE IF NOT EXISTS main_inventoryupdate (
    unifiedjob_ptr_id INTEGER NOT NULL,
    source VARCHAR(255) NOT NULL,
    source_path VARCHAR(255) NOT NULL,
    source_vars TEXT NOT NULL,
    overwrite BOOLEAN NOT NULL,
    overwrite_vars BOOLEAN NOT NULL,
    license_error BOOLEAN NOT NULL,
    inventory_source_id INTEGER NOT NULL,
    timeout INTEGER NOT NULL,
    source_project_update_id INTEGER,
    verbosity INTEGER NOT NULL,
    inventory_id INTEGER,
    custom_virtualenv VARCHAR(255),
    org_host_limit_error BOOLEAN NOT NULL,
    enabled_value TEXT NOT NULL,
    enabled_var TEXT NOT NULL,
    host_filter TEXT NOT NULL,
    scm_revision VARCHAR(255) NOT NULL,
    scm_branch VARCHAR(255) NOT NULL,
    "limit" TEXT NOT NULL
);

-- Table: main_inventoryupdateevent
CREATE TABLE IF NOT EXISTS main_inventoryupdateevent (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    inventory_update_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_job
CREATE TABLE IF NOT EXISTS main_job (
    unifiedjob_ptr_id INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    forks INTEGER NOT NULL,
    "limit" TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    extra_vars TEXT NOT NULL,
    job_tags TEXT NOT NULL,
    force_handlers BOOLEAN NOT NULL,
    skip_tags VARCHAR(255) NOT NULL,
    start_at_task VARCHAR(255) NOT NULL,
    become_enabled BOOLEAN NOT NULL,
    inventory_id INTEGER,
    job_template_id INTEGER,
    project_id INTEGER,
    allow_simultaneous BOOLEAN NOT NULL,
    artifacts TEXT NOT NULL,
    timeout INTEGER NOT NULL,
    scm_revision VARCHAR(255) NOT NULL,
    project_update_id INTEGER,
    use_fact_cache BOOLEAN NOT NULL,
    diff_mode BOOLEAN NOT NULL,
    job_slice_count INTEGER NOT NULL,
    job_slice_number INTEGER NOT NULL,
    custom_virtualenv VARCHAR(255),
    scm_branch VARCHAR(255) NOT NULL,
    webhook_credential_id INTEGER,
    webhook_guid VARCHAR(255) NOT NULL,
    webhook_service VARCHAR(255) NOT NULL,
    survey_passwords JSONB NOT NULL,
    event_queries_processed BOOLEAN NOT NULL
);

-- Table: main_jobevent
CREATE TABLE IF NOT EXISTS main_jobevent (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobevent_20250808_13
CREATE TABLE IF NOT EXISTS main_jobevent_20250808_13 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobevent_20250814_14
CREATE TABLE IF NOT EXISTS main_jobevent_20250814_14 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobevent_20250814_15
CREATE TABLE IF NOT EXISTS main_jobevent_20250814_15 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobevent_20250815_09
CREATE TABLE IF NOT EXISTS main_jobevent_20250815_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobevent_20250820_09
CREATE TABLE IF NOT EXISTS main_jobevent_20250820_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    host_id INTEGER,
    job_id INTEGER,
    uuid VARCHAR(255) NOT NULL,
    parent_uuid VARCHAR(255) NOT NULL,
    end_line INTEGER NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    start_line INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_jobhostsummary
CREATE TABLE IF NOT EXISTS main_jobhostsummary (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    host_name VARCHAR(255) NOT NULL,
    changed INTEGER NOT NULL,
    dark INTEGER NOT NULL,
    failures INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    processed INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    failed BOOLEAN NOT NULL,
    host_id INTEGER,
    job_id INTEGER NOT NULL,
    ignored INTEGER NOT NULL,
    rescued INTEGER NOT NULL,
    constructed_host_id INTEGER
);

-- Table: main_joblaunchconfig
CREATE TABLE IF NOT EXISTS main_joblaunchconfig (
    id SERIAL PRIMARY KEY,
    extra_data TEXT NOT NULL,
    inventory_id INTEGER,
    job_id INTEGER NOT NULL,
    execution_environment_id INTEGER,
    char_prompts JSONB NOT NULL,
    survey_passwords JSONB NOT NULL
);

-- Table: main_joblaunchconfig_credentials
CREATE TABLE IF NOT EXISTS main_joblaunchconfig_credentials (
    id SERIAL PRIMARY KEY,
    joblaunchconfig_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_joblaunchconfig_labels
CREATE TABLE IF NOT EXISTS main_joblaunchconfig_labels (
    id SERIAL PRIMARY KEY,
    joblaunchconfig_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_joblaunchconfiginstancegroupmembership
CREATE TABLE IF NOT EXISTS main_joblaunchconfiginstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    joblaunchconfig_id INTEGER NOT NULL
);

-- Table: main_jobtemplate
CREATE TABLE IF NOT EXISTS main_jobtemplate (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    forks INTEGER NOT NULL,
    "limit" TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    extra_vars TEXT NOT NULL,
    job_tags TEXT NOT NULL,
    force_handlers BOOLEAN NOT NULL,
    skip_tags VARCHAR(255) NOT NULL,
    start_at_task VARCHAR(255) NOT NULL,
    become_enabled BOOLEAN NOT NULL,
    host_config_key VARCHAR(255) NOT NULL,
    ask_variables_on_launch BOOLEAN NOT NULL,
    survey_enabled BOOLEAN NOT NULL,
    survey_spec JSONB NOT NULL,
    inventory_id INTEGER,
    project_id INTEGER,
    admin_role_id INTEGER,
    execute_role_id INTEGER,
    read_role_id INTEGER,
    ask_limit_on_launch BOOLEAN NOT NULL,
    ask_inventory_on_launch BOOLEAN NOT NULL,
    ask_credential_on_launch BOOLEAN NOT NULL,
    ask_job_type_on_launch BOOLEAN NOT NULL,
    ask_tags_on_launch BOOLEAN NOT NULL,
    allow_simultaneous BOOLEAN NOT NULL,
    ask_skip_tags_on_launch BOOLEAN NOT NULL,
    timeout INTEGER NOT NULL,
    use_fact_cache BOOLEAN NOT NULL,
    ask_verbosity_on_launch BOOLEAN NOT NULL,
    ask_diff_mode_on_launch BOOLEAN NOT NULL,
    diff_mode BOOLEAN NOT NULL,
    custom_virtualenv VARCHAR(255),
    job_slice_count INTEGER NOT NULL,
    ask_scm_branch_on_launch BOOLEAN NOT NULL,
    scm_branch VARCHAR(255) NOT NULL,
    webhook_credential_id INTEGER,
    webhook_key VARCHAR(255) NOT NULL,
    webhook_service VARCHAR(255) NOT NULL,
    ask_execution_environment_on_launch BOOLEAN NOT NULL,
    ask_forks_on_launch BOOLEAN NOT NULL,
    ask_instance_groups_on_launch BOOLEAN NOT NULL,
    ask_job_slice_count_on_launch BOOLEAN NOT NULL,
    ask_labels_on_launch BOOLEAN NOT NULL,
    ask_timeout_on_launch BOOLEAN NOT NULL,
    prevent_instance_group_fallback BOOLEAN NOT NULL,
    opa_query_path VARCHAR(255)
);

-- Table: main_label
CREATE TABLE IF NOT EXISTS main_label (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER NOT NULL
);

-- Table: main_notification
CREATE TABLE IF NOT EXISTS main_notification (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    status VARCHAR(255) NOT NULL,
    error TEXT NOT NULL,
    notifications_sent INTEGER NOT NULL,
    notification_type VARCHAR(255) NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT NOT NULL,
    notification_template_id INTEGER NOT NULL,
    body JSONB NOT NULL
);

-- Table: main_notificationtemplate
CREATE TABLE IF NOT EXISTS main_notificationtemplate (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    notification_type VARCHAR(255) NOT NULL,
    notification_configuration JSONB NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER,
    messages JSONB
);

-- Table: main_oauth2accesstoken
CREATE TABLE IF NOT EXISTS main_oauth2accesstoken (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL,
    expires TIMESTAMPTZ NOT NULL,
    scope TEXT NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    last_used TIMESTAMPTZ,
    application_id BIGINT,
    user_id INTEGER,
    source_refresh_token_id BIGINT,
    modified TIMESTAMPTZ NOT NULL,
    id_token_id BIGINT
);

-- Table: main_oauth2application
CREATE TABLE IF NOT EXISTS main_oauth2application (
    id BIGSERIAL PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL,
    redirect_uris TEXT NOT NULL,
    client_type VARCHAR(255) NOT NULL,
    authorization_grant_type VARCHAR(255) NOT NULL,
    client_secret VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    skip_authorization BOOLEAN NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    logo_data TEXT NOT NULL,
    user_id INTEGER,
    organization_id INTEGER,
    algorithm VARCHAR(255) NOT NULL
);

-- Table: main_organization
CREATE TABLE IF NOT EXISTS main_organization (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    admin_role_id INTEGER,
    auditor_role_id INTEGER,
    member_role_id INTEGER,
    read_role_id INTEGER,
    custom_virtualenv VARCHAR(255),
    execute_role_id INTEGER,
    job_template_admin_role_id INTEGER,
    credential_admin_role_id INTEGER,
    inventory_admin_role_id INTEGER,
    project_admin_role_id INTEGER,
    workflow_admin_role_id INTEGER,
    notification_admin_role_id INTEGER,
    max_hosts INTEGER NOT NULL,
    approval_role_id INTEGER,
    default_environment_id INTEGER,
    execution_environment_admin_role_id INTEGER,
    opa_query_path VARCHAR(255)
);

-- Table: main_organization_notification_templates_approvals
CREATE TABLE IF NOT EXISTS main_organization_notification_templates_approvals (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_organization_notification_templates_error
CREATE TABLE IF NOT EXISTS main_organization_notification_templates_error (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_organization_notification_templates_started
CREATE TABLE IF NOT EXISTS main_organization_notification_templates_started (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_organization_notification_templates_success
CREATE TABLE IF NOT EXISTS main_organization_notification_templates_success (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_organizationgalaxycredentialmembership
CREATE TABLE IF NOT EXISTS main_organizationgalaxycredentialmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    credential_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL
);

-- Table: main_organizationinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_organizationinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL
);

-- Table: main_profile
CREATE TABLE IF NOT EXISTS main_profile (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    ldap_dn VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL
);

-- Table: main_project
CREATE TABLE IF NOT EXISTS main_project (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    local_path VARCHAR(255) NOT NULL,
    scm_type VARCHAR(255) NOT NULL,
    scm_url VARCHAR(255) NOT NULL,
    scm_branch VARCHAR(255) NOT NULL,
    scm_clean BOOLEAN NOT NULL,
    scm_delete_on_update BOOLEAN NOT NULL,
    scm_update_on_launch BOOLEAN NOT NULL,
    scm_update_cache_timeout INTEGER NOT NULL,
    credential_id INTEGER,
    admin_role_id INTEGER,
    use_role_id INTEGER,
    update_role_id INTEGER,
    read_role_id INTEGER,
    timeout INTEGER NOT NULL,
    scm_revision VARCHAR(255) NOT NULL,
    playbook_files JSONB NOT NULL,
    inventory_files JSONB NOT NULL,
    custom_virtualenv VARCHAR(255),
    scm_refspec VARCHAR(255) NOT NULL,
    allow_override BOOLEAN NOT NULL,
    default_environment_id INTEGER,
    scm_track_submodules BOOLEAN NOT NULL,
    signature_validation_credential_id INTEGER
);

-- Table: main_projectupdate
CREATE TABLE IF NOT EXISTS main_projectupdate (
    unifiedjob_ptr_id INTEGER NOT NULL,
    local_path VARCHAR(255) NOT NULL,
    scm_type VARCHAR(255) NOT NULL,
    scm_url VARCHAR(255) NOT NULL,
    scm_branch VARCHAR(255) NOT NULL,
    scm_clean BOOLEAN NOT NULL,
    scm_delete_on_update BOOLEAN NOT NULL,
    credential_id INTEGER,
    project_id INTEGER NOT NULL,
    timeout INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL,
    scm_refspec VARCHAR(255) NOT NULL,
    scm_revision VARCHAR(255) NOT NULL,
    job_tags VARCHAR(255) NOT NULL,
    scm_track_submodules BOOLEAN NOT NULL
);

-- Table: main_projectupdateevent
CREATE TABLE IF NOT EXISTS main_projectupdateevent (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    project_update_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_projectupdateevent_20250808_13
CREATE TABLE IF NOT EXISTS main_projectupdateevent_20250808_13 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    project_update_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_projectupdateevent_20250815_09
CREATE TABLE IF NOT EXISTS main_projectupdateevent_20250815_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    failed BOOLEAN NOT NULL,
    changed BOOLEAN NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    playbook VARCHAR(255) NOT NULL,
    play VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    task VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    project_update_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_rbac_role_ancestors
CREATE TABLE IF NOT EXISTS main_rbac_role_ancestors (
    id SERIAL PRIMARY KEY,
    role_field TEXT NOT NULL,
    content_type_id INTEGER NOT NULL,
    object_id INTEGER NOT NULL,
    ancestor_id INTEGER NOT NULL,
    descendent_id INTEGER NOT NULL
);

-- Table: main_rbac_roles
CREATE TABLE IF NOT EXISTS main_rbac_roles (
    id SERIAL PRIMARY KEY,
    role_field TEXT NOT NULL,
    singleton_name TEXT,
    implicit_parents TEXT NOT NULL,
    content_type_id INTEGER,
    object_id INTEGER
);

-- Table: main_rbac_roles_members
CREATE TABLE IF NOT EXISTS main_rbac_roles_members (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL
);

-- Table: main_rbac_roles_parents
CREATE TABLE IF NOT EXISTS main_rbac_roles_parents (
    id SERIAL PRIMARY KEY,
    from_role_id INTEGER NOT NULL,
    to_role_id INTEGER NOT NULL
);

-- Table: main_receptoraddress
CREATE TABLE IF NOT EXISTS main_receptoraddress (
    id SERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    websocket_path VARCHAR(255) NOT NULL,
    protocol VARCHAR(255) NOT NULL,
    is_internal BOOLEAN NOT NULL,
    canonical BOOLEAN NOT NULL,
    peers_from_control_nodes BOOLEAN NOT NULL,
    instance_id INTEGER NOT NULL
);

-- Table: main_schedule
CREATE TABLE IF NOT EXISTS main_schedule (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL,
    dtstart TIMESTAMPTZ,
    dtend TIMESTAMPTZ,
    rrule TEXT NOT NULL,
    next_run TIMESTAMPTZ,
    extra_data TEXT NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    unified_job_template_id INTEGER NOT NULL,
    char_prompts JSONB NOT NULL,
    inventory_id INTEGER,
    survey_passwords JSONB NOT NULL,
    execution_environment_id INTEGER
);

-- Table: main_schedule_credentials
CREATE TABLE IF NOT EXISTS main_schedule_credentials (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_schedule_labels
CREATE TABLE IF NOT EXISTS main_schedule_labels (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_scheduleinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_scheduleinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL
);

-- Table: main_smartinventorymembership
CREATE TABLE IF NOT EXISTS main_smartinventorymembership (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL
);

-- Table: main_systemjob
CREATE TABLE IF NOT EXISTS main_systemjob (
    unifiedjob_ptr_id INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL,
    extra_vars TEXT NOT NULL,
    system_job_template_id INTEGER
);

-- Table: main_systemjobevent
CREATE TABLE IF NOT EXISTS main_systemjobevent (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250722_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250722_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250811_08
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250811_08 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250812_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250812_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250815_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250815_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250818_08
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250818_08 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250819_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250819_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250822_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250822_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250825_08
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250825_08 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250826_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250826_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250829_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250829_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250901_08
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250901_08 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20250902_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20250902_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20251014_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20251014_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20251017_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20251017_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobevent_20251104_09
CREATE TABLE IF NOT EXISTS main_systemjobevent_20251104_09 (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ,
    modified TIMESTAMPTZ NOT NULL,
    event_data TEXT NOT NULL,
    uuid VARCHAR(255) NOT NULL,
    counter INTEGER NOT NULL,
    stdout TEXT NOT NULL,
    verbosity INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    system_job_id INTEGER NOT NULL,
    job_created TIMESTAMPTZ NOT NULL
);

-- Table: main_systemjobtemplate
CREATE TABLE IF NOT EXISTS main_systemjobtemplate (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    job_type VARCHAR(255) NOT NULL
);

-- Table: main_team
CREATE TABLE IF NOT EXISTS main_team (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    organization_id INTEGER NOT NULL,
    admin_role_id INTEGER,
    member_role_id INTEGER,
    read_role_id INTEGER
);

-- Table: main_towerschedulestate
CREATE TABLE IF NOT EXISTS main_towerschedulestate (
    id SERIAL PRIMARY KEY,
    schedule_last_run TIMESTAMPTZ NOT NULL
);

-- Table: main_unifiedjob
CREATE TABLE IF NOT EXISTS main_unifiedjob (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    old_pk INTEGER,
    launch_type VARCHAR(255) NOT NULL,
    cancel_flag BOOLEAN NOT NULL,
    status VARCHAR(255) NOT NULL,
    failed BOOLEAN NOT NULL,
    started TIMESTAMPTZ,
    finished TIMESTAMPTZ,
    elapsed NUMERIC NOT NULL,
    job_args TEXT NOT NULL,
    job_cwd VARCHAR(255) NOT NULL,
    job_explanation TEXT NOT NULL,
    start_args TEXT NOT NULL,
    result_stdout_text TEXT,
    result_traceback TEXT NOT NULL,
    celery_task_id VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    modified_by_id INTEGER,
    polymorphic_ctype_id INTEGER,
    schedule_id INTEGER,
    unified_job_template_id INTEGER,
    execution_node TEXT NOT NULL,
    instance_group_id INTEGER,
    emitted_events INTEGER NOT NULL,
    controller_node TEXT NOT NULL,
    canceled_on TIMESTAMPTZ,
    dependencies_processed BOOLEAN NOT NULL,
    organization_id INTEGER,
    execution_environment_id INTEGER,
    installed_collections JSONB NOT NULL,
    ansible_version VARCHAR(255) NOT NULL,
    work_unit_id VARCHAR(255),
    host_status_counts JSONB,
    preferred_instance_groups_cache JSONB,
    task_impact INTEGER NOT NULL,
    job_env JSONB NOT NULL
);

-- Table: main_unifiedjob_credentials
CREATE TABLE IF NOT EXISTS main_unifiedjob_credentials (
    id SERIAL PRIMARY KEY,
    unifiedjob_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_unifiedjob_dependent_jobs
CREATE TABLE IF NOT EXISTS main_unifiedjob_dependent_jobs (
    id SERIAL PRIMARY KEY,
    from_unifiedjob_id INTEGER NOT NULL,
    to_unifiedjob_id INTEGER NOT NULL
);

-- Table: main_unifiedjob_labels
CREATE TABLE IF NOT EXISTS main_unifiedjob_labels (
    id SERIAL PRIMARY KEY,
    unifiedjob_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_unifiedjob_notifications
CREATE TABLE IF NOT EXISTS main_unifiedjob_notifications (
    id SERIAL PRIMARY KEY,
    unifiedjob_id INTEGER NOT NULL,
    notification_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplate
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    name VARCHAR(255) NOT NULL,
    old_pk INTEGER,
    last_job_failed BOOLEAN NOT NULL,
    last_job_run TIMESTAMPTZ,
    next_job_run TIMESTAMPTZ,
    status VARCHAR(255) NOT NULL,
    created_by_id INTEGER,
    current_job_id INTEGER,
    last_job_id INTEGER,
    modified_by_id INTEGER,
    next_schedule_id INTEGER,
    polymorphic_ctype_id INTEGER,
    organization_id INTEGER,
    execution_environment_id INTEGER,
    org_unique BOOLEAN NOT NULL
);

-- Table: main_unifiedjobtemplate_credentials
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate_credentials (
    id SERIAL PRIMARY KEY,
    unifiedjobtemplate_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplate_labels
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate_labels (
    id SERIAL PRIMARY KEY,
    unifiedjobtemplate_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplate_notification_templates_error
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate_notification_templates_error (
    id SERIAL PRIMARY KEY,
    unifiedjobtemplate_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplate_notification_templates_started
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate_notification_templates_started (
    id SERIAL PRIMARY KEY,
    unifiedjobtemplate_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplate_notification_templates_success
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplate_notification_templates_success (
    id SERIAL PRIMARY KEY,
    unifiedjobtemplate_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_unifiedjobtemplateinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_unifiedjobtemplateinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    unifiedjobtemplate_id INTEGER NOT NULL
);

-- Table: main_usersessionmembership
CREATE TABLE IF NOT EXISTS main_usersessionmembership (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL
);

-- Table: main_workflowapproval
CREATE TABLE IF NOT EXISTS main_workflowapproval (
    unifiedjob_ptr_id INTEGER NOT NULL,
    workflow_approval_template_id INTEGER,
    timeout INTEGER NOT NULL,
    timed_out BOOLEAN NOT NULL,
    approved_or_denied_by_id INTEGER,
    expires TIMESTAMPTZ
);

-- Table: main_workflowapprovaltemplate
CREATE TABLE IF NOT EXISTS main_workflowapprovaltemplate (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    timeout INTEGER NOT NULL
);

-- Table: main_workflowjob
CREATE TABLE IF NOT EXISTS main_workflowjob (
    unifiedjob_ptr_id INTEGER NOT NULL,
    extra_vars TEXT NOT NULL,
    workflow_job_template_id INTEGER,
    allow_simultaneous BOOLEAN NOT NULL,
    is_sliced_job BOOLEAN NOT NULL,
    job_template_id INTEGER,
    inventory_id INTEGER,
    webhook_credential_id INTEGER,
    webhook_guid VARCHAR(255) NOT NULL,
    webhook_service VARCHAR(255) NOT NULL,
    is_bulk_job BOOLEAN NOT NULL,
    char_prompts JSONB NOT NULL,
    survey_passwords JSONB NOT NULL
);

-- Table: main_workflowjobinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_workflowjobinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_workflowjobnode
CREATE TABLE IF NOT EXISTS main_workflowjobnode (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    job_id INTEGER,
    unified_job_template_id INTEGER,
    workflow_job_id INTEGER,
    inventory_id INTEGER,
    ancestor_artifacts TEXT NOT NULL,
    extra_data TEXT NOT NULL,
    do_not_run BOOLEAN NOT NULL,
    all_parents_must_converge BOOLEAN NOT NULL,
    identifier VARCHAR(255) NOT NULL,
    execution_environment_id INTEGER,
    char_prompts JSONB NOT NULL,
    survey_passwords JSONB NOT NULL
);

-- Table: main_workflowjobnode_always_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobnode_always_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobnode_id INTEGER NOT NULL,
    to_workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_workflowjobnode_credentials
CREATE TABLE IF NOT EXISTS main_workflowjobnode_credentials (
    id SERIAL PRIMARY KEY,
    workflowjobnode_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_workflowjobnode_failure_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobnode_failure_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobnode_id INTEGER NOT NULL,
    to_workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_workflowjobnode_labels
CREATE TABLE IF NOT EXISTS main_workflowjobnode_labels (
    id SERIAL PRIMARY KEY,
    workflowjobnode_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_workflowjobnode_success_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobnode_success_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobnode_id INTEGER NOT NULL,
    to_workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_workflowjobnodebaseinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_workflowjobnodebaseinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    workflowjobnode_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplate
CREATE TABLE IF NOT EXISTS main_workflowjobtemplate (
    unifiedjobtemplate_ptr_id INTEGER NOT NULL,
    extra_vars TEXT NOT NULL,
    admin_role_id INTEGER,
    execute_role_id INTEGER,
    read_role_id INTEGER,
    survey_enabled BOOLEAN NOT NULL,
    survey_spec JSONB NOT NULL,
    allow_simultaneous BOOLEAN NOT NULL,
    ask_variables_on_launch BOOLEAN NOT NULL,
    ask_inventory_on_launch BOOLEAN NOT NULL,
    inventory_id INTEGER,
    approval_role_id INTEGER,
    ask_limit_on_launch BOOLEAN NOT NULL,
    ask_scm_branch_on_launch BOOLEAN NOT NULL,
    char_prompts JSONB NOT NULL,
    webhook_credential_id INTEGER,
    webhook_key VARCHAR(255) NOT NULL,
    webhook_service VARCHAR(255) NOT NULL,
    ask_labels_on_launch BOOLEAN NOT NULL,
    ask_skip_tags_on_launch BOOLEAN NOT NULL,
    ask_tags_on_launch BOOLEAN NOT NULL
);

-- Table: main_workflowjobtemplate_notification_templates_approvals
CREATE TABLE IF NOT EXISTS main_workflowjobtemplate_notification_templates_approvals (
    id SERIAL PRIMARY KEY,
    workflowjobtemplate_id INTEGER NOT NULL,
    notificationtemplate_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenode
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode (
    id SERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    unified_job_template_id INTEGER,
    workflow_job_template_id INTEGER NOT NULL,
    char_prompts JSONB NOT NULL,
    inventory_id INTEGER,
    extra_data TEXT NOT NULL,
    survey_passwords JSONB NOT NULL,
    all_parents_must_converge BOOLEAN NOT NULL,
    identifier VARCHAR(255) NOT NULL,
    execution_environment_id INTEGER
);

-- Table: main_workflowjobtemplatenode_always_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode_always_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobtemplatenode_id INTEGER NOT NULL,
    to_workflowjobtemplatenode_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenode_credentials
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode_credentials (
    id SERIAL PRIMARY KEY,
    workflowjobtemplatenode_id INTEGER NOT NULL,
    credential_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenode_failure_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode_failure_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobtemplatenode_id INTEGER NOT NULL,
    to_workflowjobtemplatenode_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenode_labels
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode_labels (
    id SERIAL PRIMARY KEY,
    workflowjobtemplatenode_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenode_success_nodes
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenode_success_nodes (
    id SERIAL PRIMARY KEY,
    from_workflowjobtemplatenode_id INTEGER NOT NULL,
    to_workflowjobtemplatenode_id INTEGER NOT NULL
);

-- Table: main_workflowjobtemplatenodebaseinstancegroupmembership
CREATE TABLE IF NOT EXISTS main_workflowjobtemplatenodebaseinstancegroupmembership (
    id SERIAL PRIMARY KEY,
    position INTEGER,
    instancegroup_id INTEGER NOT NULL,
    workflowjobtemplatenode_id INTEGER NOT NULL
);

-- Table: oauth2_provider_grant
CREATE TABLE IF NOT EXISTS oauth2_provider_grant (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(255) NOT NULL,
    expires TIMESTAMPTZ NOT NULL,
    redirect_uri TEXT NOT NULL,
    scope TEXT NOT NULL,
    application_id BIGINT NOT NULL,
    user_id INTEGER NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    code_challenge VARCHAR(255) NOT NULL,
    code_challenge_method VARCHAR(255) NOT NULL,
    nonce VARCHAR(255) NOT NULL,
    claims TEXT NOT NULL
);

-- Table: oauth2_provider_idtoken
CREATE TABLE IF NOT EXISTS oauth2_provider_idtoken (
    id BIGSERIAL PRIMARY KEY,
    jti UUID NOT NULL,
    expires TIMESTAMPTZ NOT NULL,
    scope TEXT NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    application_id BIGINT,
    user_id INTEGER
);

-- Table: oauth2_provider_refreshtoken
CREATE TABLE IF NOT EXISTS oauth2_provider_refreshtoken (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL,
    access_token_id BIGINT,
    application_id BIGINT NOT NULL,
    user_id INTEGER NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    revoked TIMESTAMPTZ
);

-- Table: social_auth_association
CREATE TABLE IF NOT EXISTS social_auth_association (
    id BIGSERIAL PRIMARY KEY,
    server_url VARCHAR(255) NOT NULL,
    handle VARCHAR(255) NOT NULL,
    secret VARCHAR(255) NOT NULL,
    issued INTEGER NOT NULL,
    lifetime INTEGER NOT NULL,
    assoc_type VARCHAR(255) NOT NULL
);

-- Table: social_auth_code
CREATE TABLE IF NOT EXISTS social_auth_code (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(255) NOT NULL,
    verified BOOLEAN NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

-- Table: social_auth_nonce
CREATE TABLE IF NOT EXISTS social_auth_nonce (
    id BIGSERIAL PRIMARY KEY,
    server_url VARCHAR(255) NOT NULL,
    timestamp INTEGER NOT NULL,
    salt VARCHAR(255) NOT NULL
);

-- Table: social_auth_partial
CREATE TABLE IF NOT EXISTS social_auth_partial (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL,
    next_step SMALLINT NOT NULL,
    backend VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL
);

-- Table: social_auth_usersocialauth
CREATE TABLE IF NOT EXISTS social_auth_usersocialauth (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(255) NOT NULL,
    uid VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    modified TIMESTAMPTZ NOT NULL,
    extra_data JSONB NOT NULL
);

-- Table: sso_userenterpriseauth
CREATE TABLE IF NOT EXISTS sso_userenterpriseauth (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL
);


-- Indices for foreign key columns
CREATE INDEX IF NOT EXISTS idx_auth_group_permissions_group_id ON auth_group_permissions(group_id);
CREATE INDEX IF NOT EXISTS idx_auth_group_permissions_permission_id ON auth_group_permissions(permission_id);
CREATE INDEX IF NOT EXISTS idx_auth_permission_content_type_id ON auth_permission(content_type_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_groups_user_id ON auth_user_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_groups_group_id ON auth_user_groups(group_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_user_permissions_user_id ON auth_user_user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_user_permissions_permission_id ON auth_user_user_permissions(permission_id);
CREATE INDEX IF NOT EXISTS idx_conf_setting_user_id ON conf_setting(user_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_dabpermission_content_type_id ON dab_rbac_dabpermission(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_objectrole_object_id ON dab_rbac_objectrole(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_objectrole_content_type_id ON dab_rbac_objectrole(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_objectrole_role_definition_id ON dab_rbac_objectrole(role_definition_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_objectrole_provides_teams_objectrole_id ON dab_rbac_objectrole_provides_teams(objectrole_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_objectrole_provides_teams_team_id ON dab_rbac_objectrole_provides_teams(team_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roledefinition_content_type_id ON dab_rbac_roledefinition(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roledefinition_created_by_id ON dab_rbac_roledefinition(created_by_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roledefinition_modified_by_id ON dab_rbac_roledefinition(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roledefinition_permissions_roledefinition_id ON dab_rbac_roledefinition_permissions(roledefinition_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roledefinition_permissions_dabpermission_id ON dab_rbac_roledefinition_permissions(dabpermission_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluation_content_type_id ON dab_rbac_roleevaluation(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluation_object_id ON dab_rbac_roleevaluation(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluation_role_id ON dab_rbac_roleevaluation(role_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluationuuid_content_type_id ON dab_rbac_roleevaluationuuid(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluationuuid_object_id ON dab_rbac_roleevaluationuuid(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleevaluationuuid_role_id ON dab_rbac_roleevaluationuuid(role_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_content_type_id ON dab_rbac_roleteamassignment(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_object_id ON dab_rbac_roleteamassignment(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_role_definition_id ON dab_rbac_roleteamassignment(role_definition_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_created_by_id ON dab_rbac_roleteamassignment(created_by_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_team_id ON dab_rbac_roleteamassignment(team_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleteamassignment_object_role_id ON dab_rbac_roleteamassignment(object_role_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_content_type_id ON dab_rbac_roleuserassignment(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_object_id ON dab_rbac_roleuserassignment(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_role_definition_id ON dab_rbac_roleuserassignment(role_definition_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_created_by_id ON dab_rbac_roleuserassignment(created_by_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_user_id ON dab_rbac_roleuserassignment(user_id);
CREATE INDEX IF NOT EXISTS idx_dab_rbac_roleuserassignment_object_role_id ON dab_rbac_roleuserassignment(object_role_id);
CREATE INDEX IF NOT EXISTS idx_dab_resource_registry_resource_object_id ON dab_resource_registry_resource(object_id);
CREATE INDEX IF NOT EXISTS idx_dab_resource_registry_resource_service_id ON dab_resource_registry_resource(service_id);
CREATE INDEX IF NOT EXISTS idx_dab_resource_registry_resource_ansible_id ON dab_resource_registry_resource(ansible_id);
CREATE INDEX IF NOT EXISTS idx_dab_resource_registry_resource_content_type_id ON dab_resource_registry_resource(content_type_id);
CREATE INDEX IF NOT EXISTS idx_dab_resource_registry_resourcetype_content_type_id ON dab_resource_registry_resourcetype(content_type_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_actor_id ON main_activitystream(actor_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_ad_hoc_command_activitystream_id ON main_activitystream_ad_hoc_command(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_ad_hoc_command_adhoccommand_id ON main_activitystream_ad_hoc_command(adhoccommand_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_credential_activitystream_id ON main_activitystream_credential(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_credential_credential_id ON main_activitystream_credential(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_credential_type_activitystream_id ON main_activitystream_credential_type(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_credential_type_credentialtype_id ON main_activitystream_credential_type(credentialtype_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_execution_environment_activitystream_id ON main_activitystream_execution_environment(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_execution_environment_executionenvironment_id ON main_activitystream_execution_environment(executionenvironment_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_group_activitystream_id ON main_activitystream_group(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_group_group_id ON main_activitystream_group(group_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_host_activitystream_id ON main_activitystream_host(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_host_host_id ON main_activitystream_host(host_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_instance_activitystream_id ON main_activitystream_instance(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_instance_instance_id ON main_activitystream_instance(instance_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_instance_group_activitystream_id ON main_activitystream_instance_group(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_instance_group_instancegroup_id ON main_activitystream_instance_group(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_activitystream_id ON main_activitystream_inventory(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_inventory_id ON main_activitystream_inventory(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_source_activitystream_id ON main_activitystream_inventory_source(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_source_inventorysource_id ON main_activitystream_inventory_source(inventorysource_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_update_activitystream_id ON main_activitystream_inventory_update(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_inventory_update_inventoryupdate_id ON main_activitystream_inventory_update(inventoryupdate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_job_activitystream_id ON main_activitystream_job(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_job_job_id ON main_activitystream_job(job_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_job_template_activitystream_id ON main_activitystream_job_template(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_job_template_jobtemplate_id ON main_activitystream_job_template(jobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_label_activitystream_id ON main_activitystream_label(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_label_label_id ON main_activitystream_label(label_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_notification_activitystream_id ON main_activitystream_notification(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_notification_notification_id ON main_activitystream_notification(notification_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_notification_template_activitystream_id ON main_activitystream_notification_template(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_notification_template_notificationtemplate_id ON main_activitystream_notification_template(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_o_auth2_access_token_activitystream_id ON main_activitystream_o_auth2_access_token(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_o_auth2_access_token_oauth2accesstoken_id ON main_activitystream_o_auth2_access_token(oauth2accesstoken_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_o_auth2_application_activitystream_id ON main_activitystream_o_auth2_application(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_o_auth2_application_oauth2application_id ON main_activitystream_o_auth2_application(oauth2application_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_organization_activitystream_id ON main_activitystream_organization(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_organization_organization_id ON main_activitystream_organization(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_project_activitystream_id ON main_activitystream_project(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_project_project_id ON main_activitystream_project(project_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_project_update_activitystream_id ON main_activitystream_project_update(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_project_update_projectupdate_id ON main_activitystream_project_update(projectupdate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_receptor_address_activitystream_id ON main_activitystream_receptor_address(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_receptor_address_receptoraddress_id ON main_activitystream_receptor_address(receptoraddress_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_role_activitystream_id ON main_activitystream_role(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_role_role_id ON main_activitystream_role(role_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_schedule_activitystream_id ON main_activitystream_schedule(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_schedule_schedule_id ON main_activitystream_schedule(schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_team_activitystream_id ON main_activitystream_team(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_team_team_id ON main_activitystream_team(team_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_unified_job_activitystream_id ON main_activitystream_unified_job(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_unified_job_unifiedjob_id ON main_activitystream_unified_job(unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_unified_job_template_activitystream_id ON main_activitystream_unified_job_template(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_unified_job_template_unifiedjobtemplate_id ON main_activitystream_unified_job_template(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_user_activitystream_id ON main_activitystream_user(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_user_user_id ON main_activitystream_user(user_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_approval_activitystream_id ON main_activitystream_workflow_approval(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_approval_workflowapproval_id ON main_activitystream_workflow_approval(workflowapproval_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_approval_template_activitystream_id ON main_activitystream_workflow_approval_template(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_approval_template_workflowapprovaltemplate_id ON main_activitystream_workflow_approval_template(workflowapprovaltemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_activitystream_id ON main_activitystream_workflow_job(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_workflowjob_id ON main_activitystream_workflow_job(workflowjob_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_node_activitystream_id ON main_activitystream_workflow_job_node(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_node_workflowjobnode_id ON main_activitystream_workflow_job_node(workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_template_activitystream_id ON main_activitystream_workflow_job_template(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_template_workflowjobtemplate_id ON main_activitystream_workflow_job_template(workflowjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_template_node_activitystream_id ON main_activitystream_workflow_job_template_node(activitystream_id);
CREATE INDEX IF NOT EXISTS idx_main_activitystream_workflow_job_template_node_workflowjobtemplatenode_id ON main_activitystream_workflow_job_template_node(workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_adhoccommand_unifiedjob_ptr_id ON main_adhoccommand(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_adhoccommand_credential_id ON main_adhoccommand(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_adhoccommand_inventory_id ON main_adhoccommand(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_adhoccommandevent_host_id ON main_adhoccommandevent(host_id);
CREATE INDEX IF NOT EXISTS idx_main_adhoccommandevent_ad_hoc_command_id ON main_adhoccommandevent(ad_hoc_command_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_created_by_id ON main_credential(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_modified_by_id ON main_credential(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_organization_id ON main_credential(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_admin_role_id ON main_credential(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_use_role_id ON main_credential(use_role_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_read_role_id ON main_credential(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_credential_credential_type_id ON main_credential(credential_type_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialinputsource_created_by_id ON main_credentialinputsource(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialinputsource_modified_by_id ON main_credentialinputsource(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialinputsource_source_credential_id ON main_credentialinputsource(source_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialinputsource_target_credential_id ON main_credentialinputsource(target_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialtype_created_by_id ON main_credentialtype(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_credentialtype_modified_by_id ON main_credentialtype(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_custominventoryscript_created_by_id ON main_custominventoryscript(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_custominventoryscript_modified_by_id ON main_custominventoryscript(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_executionenvironment_created_by_id ON main_executionenvironment(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_executionenvironment_credential_id ON main_executionenvironment(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_executionenvironment_modified_by_id ON main_executionenvironment(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_executionenvironment_organization_id ON main_executionenvironment(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_group_created_by_id ON main_group(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_group_inventory_id ON main_group(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_group_modified_by_id ON main_group(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_group_hosts_group_id ON main_group_hosts(group_id);
CREATE INDEX IF NOT EXISTS idx_main_group_hosts_host_id ON main_group_hosts(host_id);
CREATE INDEX IF NOT EXISTS idx_main_group_inventory_sources_group_id ON main_group_inventory_sources(group_id);
CREATE INDEX IF NOT EXISTS idx_main_group_inventory_sources_inventorysource_id ON main_group_inventory_sources(inventorysource_id);
CREATE INDEX IF NOT EXISTS idx_main_group_parents_from_group_id ON main_group_parents(from_group_id);
CREATE INDEX IF NOT EXISTS idx_main_group_parents_to_group_id ON main_group_parents(to_group_id);
CREATE INDEX IF NOT EXISTS idx_main_host_instance_id ON main_host(instance_id);
CREATE INDEX IF NOT EXISTS idx_main_host_created_by_id ON main_host(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_host_inventory_id ON main_host(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_host_last_job_host_summary_id ON main_host(last_job_host_summary_id);
CREATE INDEX IF NOT EXISTS idx_main_host_modified_by_id ON main_host(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_host_last_job_id ON main_host(last_job_id);
CREATE INDEX IF NOT EXISTS idx_main_host_inventory_sources_host_id ON main_host_inventory_sources(host_id);
CREATE INDEX IF NOT EXISTS idx_main_host_inventory_sources_inventorysource_id ON main_host_inventory_sources(inventorysource_id);
CREATE INDEX IF NOT EXISTS idx_main_indirectmanagednodeaudit_host_id ON main_indirectmanagednodeaudit(host_id);
CREATE INDEX IF NOT EXISTS idx_main_indirectmanagednodeaudit_inventory_id ON main_indirectmanagednodeaudit(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_indirectmanagednodeaudit_job_id ON main_indirectmanagednodeaudit(job_id);
CREATE INDEX IF NOT EXISTS idx_main_indirectmanagednodeaudit_organization_id ON main_indirectmanagednodeaudit(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_credential_id ON main_instancegroup(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_admin_role_id ON main_instancegroup(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_read_role_id ON main_instancegroup(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_use_role_id ON main_instancegroup(use_role_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_instances_instancegroup_id ON main_instancegroup_instances(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_instancegroup_instances_instance_id ON main_instancegroup_instances(instance_id);
CREATE INDEX IF NOT EXISTS idx_main_instancelink_source_id ON main_instancelink(source_id);
CREATE INDEX IF NOT EXISTS idx_main_instancelink_target_id ON main_instancelink(target_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_created_by_id ON main_inventory(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_modified_by_id ON main_inventory(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_organization_id ON main_inventory(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_admin_role_id ON main_inventory(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_adhoc_role_id ON main_inventory(adhoc_role_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_update_role_id ON main_inventory(update_role_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_use_role_id ON main_inventory(use_role_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_read_role_id ON main_inventory(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_labels_inventory_id ON main_inventory_labels(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventory_labels_label_id ON main_inventory_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryconstructedinventorymembership_constructed_inventory_id ON main_inventoryconstructedinventorymembership(constructed_inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryconstructedinventorymembership_input_inventory_id ON main_inventoryconstructedinventorymembership(input_inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventorygroupvariableswithhistory_group_id ON main_inventorygroupvariableswithhistory(group_id);
CREATE INDEX IF NOT EXISTS idx_main_inventorygroupvariableswithhistory_inventory_id ON main_inventorygroupvariableswithhistory(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryinstancegroupmembership_instancegroup_id ON main_inventoryinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryinstancegroupmembership_inventory_id ON main_inventoryinstancegroupmembership(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventorysource_unifiedjobtemplate_ptr_id ON main_inventorysource(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_inventorysource_inventory_id ON main_inventorysource(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventorysource_source_project_id ON main_inventorysource(source_project_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryupdate_unifiedjob_ptr_id ON main_inventoryupdate(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryupdate_inventory_source_id ON main_inventoryupdate(inventory_source_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryupdate_source_project_update_id ON main_inventoryupdate(source_project_update_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryupdate_inventory_id ON main_inventoryupdate(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_inventoryupdateevent_inventory_update_id ON main_inventoryupdateevent(inventory_update_id);
CREATE INDEX IF NOT EXISTS idx_main_job_unifiedjob_ptr_id ON main_job(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_job_inventory_id ON main_job(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_job_job_template_id ON main_job(job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_job_project_id ON main_job(project_id);
CREATE INDEX IF NOT EXISTS idx_main_job_project_update_id ON main_job(project_update_id);
CREATE INDEX IF NOT EXISTS idx_main_job_webhook_credential_id ON main_job(webhook_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_host_id ON main_jobevent(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_job_id ON main_jobevent(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250808_13_host_id ON main_jobevent_20250808_13(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250808_13_job_id ON main_jobevent_20250808_13(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250814_14_host_id ON main_jobevent_20250814_14(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250814_14_job_id ON main_jobevent_20250814_14(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250814_15_host_id ON main_jobevent_20250814_15(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250814_15_job_id ON main_jobevent_20250814_15(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250815_09_host_id ON main_jobevent_20250815_09(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250815_09_job_id ON main_jobevent_20250815_09(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250820_09_host_id ON main_jobevent_20250820_09(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobevent_20250820_09_job_id ON main_jobevent_20250820_09(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobhostsummary_host_id ON main_jobhostsummary(host_id);
CREATE INDEX IF NOT EXISTS idx_main_jobhostsummary_job_id ON main_jobhostsummary(job_id);
CREATE INDEX IF NOT EXISTS idx_main_jobhostsummary_constructed_host_id ON main_jobhostsummary(constructed_host_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_inventory_id ON main_joblaunchconfig(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_job_id ON main_joblaunchconfig(job_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_execution_environment_id ON main_joblaunchconfig(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_credentials_joblaunchconfig_id ON main_joblaunchconfig_credentials(joblaunchconfig_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_credentials_credential_id ON main_joblaunchconfig_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_labels_joblaunchconfig_id ON main_joblaunchconfig_labels(joblaunchconfig_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfig_labels_label_id ON main_joblaunchconfig_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfiginstancegroupmembership_instancegroup_id ON main_joblaunchconfiginstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_joblaunchconfiginstancegroupmembership_joblaunchconfig_id ON main_joblaunchconfiginstancegroupmembership(joblaunchconfig_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_unifiedjobtemplate_ptr_id ON main_jobtemplate(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_inventory_id ON main_jobtemplate(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_project_id ON main_jobtemplate(project_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_admin_role_id ON main_jobtemplate(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_execute_role_id ON main_jobtemplate(execute_role_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_read_role_id ON main_jobtemplate(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_jobtemplate_webhook_credential_id ON main_jobtemplate(webhook_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_label_created_by_id ON main_label(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_label_modified_by_id ON main_label(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_label_organization_id ON main_label(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_notification_notification_template_id ON main_notification(notification_template_id);
CREATE INDEX IF NOT EXISTS idx_main_notificationtemplate_created_by_id ON main_notificationtemplate(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_notificationtemplate_modified_by_id ON main_notificationtemplate(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_notificationtemplate_organization_id ON main_notificationtemplate(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2accesstoken_application_id ON main_oauth2accesstoken(application_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2accesstoken_user_id ON main_oauth2accesstoken(user_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2accesstoken_source_refresh_token_id ON main_oauth2accesstoken(source_refresh_token_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2accesstoken_id_token_id ON main_oauth2accesstoken(id_token_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2application_client_id ON main_oauth2application(client_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2application_user_id ON main_oauth2application(user_id);
CREATE INDEX IF NOT EXISTS idx_main_oauth2application_organization_id ON main_oauth2application(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_created_by_id ON main_organization(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_modified_by_id ON main_organization(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_admin_role_id ON main_organization(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_auditor_role_id ON main_organization(auditor_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_member_role_id ON main_organization(member_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_read_role_id ON main_organization(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_execute_role_id ON main_organization(execute_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_job_template_admin_role_id ON main_organization(job_template_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_credential_admin_role_id ON main_organization(credential_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_inventory_admin_role_id ON main_organization(inventory_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_project_admin_role_id ON main_organization(project_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_workflow_admin_role_id ON main_organization(workflow_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_admin_role_id ON main_organization(notification_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_approval_role_id ON main_organization(approval_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_default_environment_id ON main_organization(default_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_execution_environment_admin_role_id ON main_organization(execution_environment_admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_approvals_organization_id ON main_organization_notification_templates_approvals(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_approvals_notificationtemplate_id ON main_organization_notification_templates_approvals(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_error_organization_id ON main_organization_notification_templates_error(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_error_notificationtemplate_id ON main_organization_notification_templates_error(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_started_organization_id ON main_organization_notification_templates_started(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_started_notificationtemplate_id ON main_organization_notification_templates_started(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_success_organization_id ON main_organization_notification_templates_success(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organization_notification_templates_success_notificationtemplate_id ON main_organization_notification_templates_success(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_organizationgalaxycredentialmembership_credential_id ON main_organizationgalaxycredentialmembership(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_organizationgalaxycredentialmembership_organization_id ON main_organizationgalaxycredentialmembership(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_organizationinstancegroupmembership_instancegroup_id ON main_organizationinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_organizationinstancegroupmembership_organization_id ON main_organizationinstancegroupmembership(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_profile_user_id ON main_profile(user_id);
CREATE INDEX IF NOT EXISTS idx_main_project_unifiedjobtemplate_ptr_id ON main_project(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_project_credential_id ON main_project(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_project_admin_role_id ON main_project(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_project_use_role_id ON main_project(use_role_id);
CREATE INDEX IF NOT EXISTS idx_main_project_update_role_id ON main_project(update_role_id);
CREATE INDEX IF NOT EXISTS idx_main_project_read_role_id ON main_project(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_project_default_environment_id ON main_project(default_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_project_signature_validation_credential_id ON main_project(signature_validation_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdate_unifiedjob_ptr_id ON main_projectupdate(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdate_credential_id ON main_projectupdate(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdate_project_id ON main_projectupdate(project_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdateevent_project_update_id ON main_projectupdateevent(project_update_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdateevent_20250808_13_project_update_id ON main_projectupdateevent_20250808_13(project_update_id);
CREATE INDEX IF NOT EXISTS idx_main_projectupdateevent_20250815_09_project_update_id ON main_projectupdateevent_20250815_09(project_update_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_role_ancestors_content_type_id ON main_rbac_role_ancestors(content_type_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_role_ancestors_object_id ON main_rbac_role_ancestors(object_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_role_ancestors_ancestor_id ON main_rbac_role_ancestors(ancestor_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_role_ancestors_descendent_id ON main_rbac_role_ancestors(descendent_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_content_type_id ON main_rbac_roles(content_type_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_object_id ON main_rbac_roles(object_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_members_role_id ON main_rbac_roles_members(role_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_members_user_id ON main_rbac_roles_members(user_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_parents_from_role_id ON main_rbac_roles_parents(from_role_id);
CREATE INDEX IF NOT EXISTS idx_main_rbac_roles_parents_to_role_id ON main_rbac_roles_parents(to_role_id);
CREATE INDEX IF NOT EXISTS idx_main_receptoraddress_instance_id ON main_receptoraddress(instance_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_created_by_id ON main_schedule(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_modified_by_id ON main_schedule(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_unified_job_template_id ON main_schedule(unified_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_inventory_id ON main_schedule(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_execution_environment_id ON main_schedule(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_credentials_schedule_id ON main_schedule_credentials(schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_credentials_credential_id ON main_schedule_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_labels_schedule_id ON main_schedule_labels(schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_schedule_labels_label_id ON main_schedule_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_scheduleinstancegroupmembership_instancegroup_id ON main_scheduleinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_scheduleinstancegroupmembership_schedule_id ON main_scheduleinstancegroupmembership(schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_smartinventorymembership_host_id ON main_smartinventorymembership(host_id);
CREATE INDEX IF NOT EXISTS idx_main_smartinventorymembership_inventory_id ON main_smartinventorymembership(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjob_unifiedjob_ptr_id ON main_systemjob(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjob_system_job_template_id ON main_systemjob(system_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_system_job_id ON main_systemjobevent(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250722_09_system_job_id ON main_systemjobevent_20250722_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250811_08_system_job_id ON main_systemjobevent_20250811_08(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250812_09_system_job_id ON main_systemjobevent_20250812_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250815_09_system_job_id ON main_systemjobevent_20250815_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250818_08_system_job_id ON main_systemjobevent_20250818_08(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250819_09_system_job_id ON main_systemjobevent_20250819_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250822_09_system_job_id ON main_systemjobevent_20250822_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250825_08_system_job_id ON main_systemjobevent_20250825_08(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250826_09_system_job_id ON main_systemjobevent_20250826_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250829_09_system_job_id ON main_systemjobevent_20250829_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250901_08_system_job_id ON main_systemjobevent_20250901_08(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20250902_09_system_job_id ON main_systemjobevent_20250902_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20251014_09_system_job_id ON main_systemjobevent_20251014_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20251017_09_system_job_id ON main_systemjobevent_20251017_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobevent_20251104_09_system_job_id ON main_systemjobevent_20251104_09(system_job_id);
CREATE INDEX IF NOT EXISTS idx_main_systemjobtemplate_unifiedjobtemplate_ptr_id ON main_systemjobtemplate(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_team_created_by_id ON main_team(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_team_modified_by_id ON main_team(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_team_organization_id ON main_team(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_team_admin_role_id ON main_team(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_team_member_role_id ON main_team(member_role_id);
CREATE INDEX IF NOT EXISTS idx_main_team_read_role_id ON main_team(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_celery_task_id ON main_unifiedjob(celery_task_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_created_by_id ON main_unifiedjob(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_modified_by_id ON main_unifiedjob(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_polymorphic_ctype_id ON main_unifiedjob(polymorphic_ctype_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_schedule_id ON main_unifiedjob(schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_unified_job_template_id ON main_unifiedjob(unified_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_instance_group_id ON main_unifiedjob(instance_group_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_organization_id ON main_unifiedjob(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_execution_environment_id ON main_unifiedjob(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_work_unit_id ON main_unifiedjob(work_unit_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_credentials_unifiedjob_id ON main_unifiedjob_credentials(unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_credentials_credential_id ON main_unifiedjob_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_dependent_jobs_from_unifiedjob_id ON main_unifiedjob_dependent_jobs(from_unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_dependent_jobs_to_unifiedjob_id ON main_unifiedjob_dependent_jobs(to_unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_labels_unifiedjob_id ON main_unifiedjob_labels(unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_labels_label_id ON main_unifiedjob_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_notifications_unifiedjob_id ON main_unifiedjob_notifications(unifiedjob_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjob_notifications_notification_id ON main_unifiedjob_notifications(notification_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_created_by_id ON main_unifiedjobtemplate(created_by_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_current_job_id ON main_unifiedjobtemplate(current_job_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_last_job_id ON main_unifiedjobtemplate(last_job_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_modified_by_id ON main_unifiedjobtemplate(modified_by_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_next_schedule_id ON main_unifiedjobtemplate(next_schedule_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_polymorphic_ctype_id ON main_unifiedjobtemplate(polymorphic_ctype_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_organization_id ON main_unifiedjobtemplate(organization_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_execution_environment_id ON main_unifiedjobtemplate(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_credentials_unifiedjobtemplate_id ON main_unifiedjobtemplate_credentials(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_credentials_credential_id ON main_unifiedjobtemplate_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_labels_unifiedjobtemplate_id ON main_unifiedjobtemplate_labels(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_labels_label_id ON main_unifiedjobtemplate_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_error_unifiedjobtemplate_id ON main_unifiedjobtemplate_notification_templates_error(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_error_notificationtemplate_id ON main_unifiedjobtemplate_notification_templates_error(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_started_unifiedjobtemplate_id ON main_unifiedjobtemplate_notification_templates_started(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_started_notificationtemplate_id ON main_unifiedjobtemplate_notification_templates_started(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_success_unifiedjobtemplate_id ON main_unifiedjobtemplate_notification_templates_success(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplate_notification_templates_success_notificationtemplate_id ON main_unifiedjobtemplate_notification_templates_success(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplateinstancegroupmembership_instancegroup_id ON main_unifiedjobtemplateinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_unifiedjobtemplateinstancegroupmembership_unifiedjobtemplate_id ON main_unifiedjobtemplateinstancegroupmembership(unifiedjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_usersessionmembership_session_id ON main_usersessionmembership(session_id);
CREATE INDEX IF NOT EXISTS idx_main_usersessionmembership_user_id ON main_usersessionmembership(user_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowapproval_unifiedjob_ptr_id ON main_workflowapproval(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowapproval_workflow_approval_template_id ON main_workflowapproval(workflow_approval_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowapproval_approved_or_denied_by_id ON main_workflowapproval(approved_or_denied_by_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowapprovaltemplate_unifiedjobtemplate_ptr_id ON main_workflowapprovaltemplate(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjob_unifiedjob_ptr_id ON main_workflowjob(unifiedjob_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjob_workflow_job_template_id ON main_workflowjob(workflow_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjob_job_template_id ON main_workflowjob(job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjob_inventory_id ON main_workflowjob(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjob_webhook_credential_id ON main_workflowjob(webhook_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobinstancegroupmembership_instancegroup_id ON main_workflowjobinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobinstancegroupmembership_workflowjobnode_id ON main_workflowjobinstancegroupmembership(workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_job_id ON main_workflowjobnode(job_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_unified_job_template_id ON main_workflowjobnode(unified_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_workflow_job_id ON main_workflowjobnode(workflow_job_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_inventory_id ON main_workflowjobnode(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_execution_environment_id ON main_workflowjobnode(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_always_nodes_from_workflowjobnode_id ON main_workflowjobnode_always_nodes(from_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_always_nodes_to_workflowjobnode_id ON main_workflowjobnode_always_nodes(to_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_credentials_workflowjobnode_id ON main_workflowjobnode_credentials(workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_credentials_credential_id ON main_workflowjobnode_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_failure_nodes_from_workflowjobnode_id ON main_workflowjobnode_failure_nodes(from_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_failure_nodes_to_workflowjobnode_id ON main_workflowjobnode_failure_nodes(to_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_labels_workflowjobnode_id ON main_workflowjobnode_labels(workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_labels_label_id ON main_workflowjobnode_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_success_nodes_from_workflowjobnode_id ON main_workflowjobnode_success_nodes(from_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnode_success_nodes_to_workflowjobnode_id ON main_workflowjobnode_success_nodes(to_workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnodebaseinstancegroupmembership_instancegroup_id ON main_workflowjobnodebaseinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobnodebaseinstancegroupmembership_workflowjobnode_id ON main_workflowjobnodebaseinstancegroupmembership(workflowjobnode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_unifiedjobtemplate_ptr_id ON main_workflowjobtemplate(unifiedjobtemplate_ptr_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_admin_role_id ON main_workflowjobtemplate(admin_role_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_execute_role_id ON main_workflowjobtemplate(execute_role_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_read_role_id ON main_workflowjobtemplate(read_role_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_inventory_id ON main_workflowjobtemplate(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_approval_role_id ON main_workflowjobtemplate(approval_role_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_webhook_credential_id ON main_workflowjobtemplate(webhook_credential_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_notification_templates_approvals_workflowjobtemplate_id ON main_workflowjobtemplate_notification_templates_approvals(workflowjobtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplate_notification_templates_approvals_notificationtemplate_id ON main_workflowjobtemplate_notification_templates_approvals(notificationtemplate_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_unified_job_template_id ON main_workflowjobtemplatenode(unified_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_workflow_job_template_id ON main_workflowjobtemplatenode(workflow_job_template_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_inventory_id ON main_workflowjobtemplatenode(inventory_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_execution_environment_id ON main_workflowjobtemplatenode(execution_environment_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_always_nodes_from_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_always_nodes(from_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_always_nodes_to_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_always_nodes(to_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_credentials_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_credentials(workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_credentials_credential_id ON main_workflowjobtemplatenode_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_failure_nodes_from_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_failure_nodes(from_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_failure_nodes_to_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_failure_nodes(to_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_labels_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_labels(workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_labels_label_id ON main_workflowjobtemplatenode_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_success_nodes_from_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_success_nodes(from_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenode_success_nodes_to_workflowjobtemplatenode_id ON main_workflowjobtemplatenode_success_nodes(to_workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenodebaseinstancegroupmembership_instancegroup_id ON main_workflowjobtemplatenodebaseinstancegroupmembership(instancegroup_id);
CREATE INDEX IF NOT EXISTS idx_main_workflowjobtemplatenodebaseinstancegroupmembership_workflowjobtemplatenode_id ON main_workflowjobtemplatenodebaseinstancegroupmembership(workflowjobtemplatenode_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_grant_application_id ON oauth2_provider_grant(application_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_grant_user_id ON oauth2_provider_grant(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_idtoken_application_id ON oauth2_provider_idtoken(application_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_idtoken_user_id ON oauth2_provider_idtoken(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_refreshtoken_access_token_id ON oauth2_provider_refreshtoken(access_token_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_refreshtoken_application_id ON oauth2_provider_refreshtoken(application_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_provider_refreshtoken_user_id ON oauth2_provider_refreshtoken(user_id);
CREATE INDEX IF NOT EXISTS idx_social_auth_usersocialauth_user_id ON social_auth_usersocialauth(user_id);
CREATE INDEX IF NOT EXISTS idx_sso_userenterpriseauth_user_id ON sso_userenterpriseauth(user_id);
