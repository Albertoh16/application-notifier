# Apply your filters here. Make it {} if you want no filters.
FILTERS = {
    # The seniority you are looking for (Intern, New Grad, Full Time, Part Time, Co-op, etc.)
    "position": {"Intern"},
    # Positions you want to exclude.
    "exclude position": {"Senior"},

    # The type of work you are looking for (Engineering, Developer, Software, Design, Research, etc.)
    "role": {"Engineering", "Engineer", "Developer", "Development", "Software"},
    # Roles you want to exclude.
    "exclude role": {"Network", "Networking", "IT"},

    # The specialization you want (AI, ML, Backend, Frontend, Full Stack, Cloud)
    "specialization": {},
    # Specializations you want to exclude.
    "exclude specialization": {"Data", "Mobile", "Robotics"},

    # Keywords that must appear in the qualifications (Bachelors, Bachelor's, Undergraduate, 2026, 2027, etc.)
    "qualification": {"Bachelors", "Bachelor's", "BA", "Undergraduate", "2026"},
    # Qualifications you want to exclude.
    "exclude qualification": {},

    # The industry you want to work in (Software, Healthcare, Finance, AI, etc.)
    "industry": {},
    # Industries you want to exclude.
    "exclude industry": {}
}