async def standardize_search_terms(search_input: Dict[str, str]) -> Dict[str, Dict[str, Union[str, List[str]]]]:
    """
    Standardize search terms and generate variations for semantic search.
    """
    standardized = {}
    
    # Role standardization
    if "role" in search_input:
        role = search_input["role"].lower()
        if "audit" in role:
            if "technology" in role or "tech" in role:
                standardized["role"] = {
                    "standardized": "technology audit",
                    "search_variations": [
                        "technology audit",
                        "it audit",
                        "tech audit",
                        "information technology audit"
                    ]
                }
            else:
                standardized["role"] = {
                    "standardized": "audit manager",
                    "search_variations": [
                        "audit manager",
                        "audit lead",
                        "audit team manager",
                        "auditing manager"
                    ]
                }
    
    # Location standardization
    if "location" in search_input:
        location = search_input["location"].lower()
        if location in ["ny", "nyc", "new york"]:
            standardized["location"] = {
                "standardized": "new york",
                "search_variations": ["new york", "ny", "nyc"]
            }
        elif location in ["boston", "ma", "massachusetts"]:
            standardized["location"] = {
                "standardized": "boston",
                "search_variations": ["boston", "ma", "massachusetts"]
            }
    
    # Experience level standardization
    if "experience" in search_input:
        experience = search_input["experience"].lower()
        if "manager" in experience:
            standardized["experience"] = {
                "standardized": "manager",
                "search_variations": [
                    "manager",
                    "management",
                    "managerial",
                    "team lead"
                ]
            }
        elif "senior" in experience:
            standardized["experience"] = {
                "standardized": "senior",
                "search_variations": [
                    "senior",
                    "senior level",
                    "experienced",
                    "advanced"
                ]
            }
    
    return standardized 