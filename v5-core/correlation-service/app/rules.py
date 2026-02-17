import yaml
import hashlib
import logging
from typing import List, Dict, Any, Optional
import os
import itertools

logger = logging.getLogger("rules-engine")

class Rule:
    def __init__(self, data: Dict):
        self.rule_id = data['rule_id']
        self.rule_name = data['rule_name']
        self.confidence = data['confidence']
        self.window_minutes = int(data.get('window_minutes', 15))
        self.template = data['correlation_key_template']
        self.required_fields = data.get('required_fields', [])

    def match(self, tenant_id: str, payload: Dict, timestamp: int) -> List[Dict]:
        matches = []

        # 1. Build Context (Flatten)
        context = {"tenant_id": [tenant_id]} # List for consistency

        # Add payload fields
        for k, v in payload.items():
            if isinstance(v, list):
                context[k] = v
            else:
                context[k] = [v]

        # 2. Check Required Fields & Prepare Iterables
        iterables = {}
        for field in self.required_fields:
            if field not in context or not context[field]:
                return [] # Missing required field
            iterables[field] = context[field]

        # 3. Cartesian Product of values
        keys = list(iterables.keys())
        values_product = itertools.product(*(iterables[k] for k in keys))

        for combination in values_product:
            local_ctx = dict(zip(keys, combination))

            try:
                key = self.template.format(**local_ctx)
            except KeyError:
                continue

            # 4. Deterministic Group ID
            window_ms = self.window_minutes * 60 * 1000
            window_idx = int(timestamp / window_ms) if window_ms > 0 else 0

            raw_id = f"{tenant_id}:{self.rule_id}:{key}:{window_idx}"
            group_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()

            matches.append({
                "rule_id": self.rule_id,
                "rule_name": self.rule_name,
                "confidence": self.confidence,
                "correlation_key": key,
                "group_id": group_id,
                "window_idx": window_idx,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "status": "OPEN",
                "alert_count": 1,
                "max_severity": payload.get("severity", 1)
            })

        return matches

class RuleEngine:
    def __init__(self, db_instance=None):
        self.rules = []
        self.db = db_instance
        if self.db:
            self.reload_rules()
        else:
            # Fallback to file if DB not provided (testing/legacy)
            self._load_file(os.getenv("RULES_FILE", "rules.yaml"))

    def _load_file(self, path: str):
        if not os.path.exists(path):
            logger.warning(f"Rules file not found: {path}")
            return
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'rules' in data:
                for r in data['rules']:
                    self.rules.append(Rule(r))
        logger.info(f"Loaded {len(self.rules)} rules from file")

    def reload_rules(self):
        if not self.db:
            return

        db_rules = self.db.fetch_rules()
        if not db_rules:
            logger.warning("No rules fetched from DB (or error). Keeping existing rules.")
            return

        new_rules = []
        for r in db_rules:
            new_rules.append(Rule(r))

        self.rules = new_rules
        logger.info(f"Reloaded {len(self.rules)} rules from DB")

    def evaluate(self, tenant_id: str, payload: Dict, timestamp: int) -> List[Dict]:
        all_matches = []
        for rule in self.rules:
            matches = rule.match(tenant_id, payload, timestamp)
            all_matches.extend(matches)
        return all_matches
