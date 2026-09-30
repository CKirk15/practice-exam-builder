"""DVA-C02 exam guide reference data — the single source of truth."""

QUESTIONS_PER_VIDEO = 20
EXAM = {"questions": 65, "minutes": 130, "passPct": 72}

DOMAINS = [
    {"id": 1, "name": "Development with AWS Services", "weight": 32, "tasks": {
        "1.1": "Develop code for applications hosted on AWS",
        "1.2": "Develop code for AWS Lambda",
        "1.3": "Use data stores in application development",
    }},
    {"id": 2, "name": "Security", "weight": 26, "tasks": {
        "2.1": "Implement authentication and/or authorization for applications and AWS services",
        "2.2": "Implement encryption by using AWS services",
        "2.3": "Manage sensitive data in application code",
    }},
    {"id": 3, "name": "Deployment", "weight": 24, "tasks": {
        "3.1": "Prepare application artifacts to be deployed to AWS",
        "3.2": "Test applications in development environments",
        "3.3": "Automate deployment testing",
        "3.4": "Deploy code by using AWS CI/CD services",
    }},
    {"id": 4, "name": "Troubleshooting and Optimization", "weight": 18, "tasks": {
        "4.1": "Assist in a root cause analysis",
        "4.2": "Instrument code for observability",
        "4.3": "Optimize applications by using AWS services and features",
    }},
]


def exam_quotas(total: int = EXAM["questions"]) -> dict[int, int]:
    """Largest-remainder apportionment of `total` questions by domain weight."""
    weight_sum = sum(d["weight"] for d in DOMAINS)
    exact = {d["id"]: total * d["weight"] / weight_sum for d in DOMAINS}
    quotas = {k: int(v) for k, v in exact.items()}
    leftover = total - sum(quotas.values())
    by_remainder = sorted(exact, key=lambda k: (-(exact[k] - quotas[k]), k))
    for k in by_remainder[:leftover]:
        quotas[k] += 1
    return quotas
