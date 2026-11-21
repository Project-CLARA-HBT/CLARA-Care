package temporal_access

# Translation of the published OpenFGA temporal_access condition.
active(t) if not t.condition
active(t) if {
    t.condition.name == "temporal_access"
    start := time.parse_rfc3339_ns(t.condition.context.grant_time)
    duration := time.parse_duration_ns(t.condition.context.grant_duration)
    time.parse_rfc3339_ns(input.context.current_time) < start + duration
}

matches(t) if {
    t.relation == input.relation
    active(t)
}

default check := false
check if {
    some t in data.tuples
    matches(t)
    t.user == input.user
    t.object == input.object
}

list_objects contains t.object if {
    some t in data.tuples
    matches(t)
    t.user == input.user
    startswith(t.object, concat("", [input.type, ":"]))
}

list_users contains t.user if {
    some t in data.tuples
    matches(t)
    t.object == input.object
    some f in input.user_filter
    startswith(t.user, concat("", [f.type, ":"]))
}
