import pytest

from app.services.scanner import scan_repo


def write_files(root, files):
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def scan(tmp_path, files):
    write_files(tmp_path, files)
    findings, _hits, _texts, _total = scan_repo(tmp_path)
    return findings


def for_rule(findings, rule_id):
    return [f for f in findings if f["rule_id"] == rule_id]


def severities(findings):
    return [f["severity"] for f in findings]


AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


def test_aws_key_detected_as_critical(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": f'aws_access_key_id = "{AWS_KEY}"\n'}), "SECRET_AWS_KEY"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"
    assert findings[0]["category"] == "secrets"


def test_aws_key_with_invalid_base32_char_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": 'aws_access_key_id = "AKIAIOSFODNN7EXAMPL1"\n'}), "SECRET_AWS_KEY"
    )
    assert findings == []


def test_openai_key_detected_as_critical(tmp_path):
    token = "sk-" + ("a" * 20) + "T3BlbkFJ" + ("b" * 20)
    findings = for_rule(
        scan(tmp_path, {"app.py": f'openai_api_key = "{token}"\n'}), "SECRET_OPENAI_KEY"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_openai_key_without_t3blbkfj_marker_not_detected(tmp_path):
    token = "sk-" + ("a" * 20) + "T3BlbkF" + ("b" * 20)
    findings = for_rule(
        scan(tmp_path, {"app.py": f'openai_api_key = "{token}"\n'}), "SECRET_OPENAI_KEY"
    )
    assert findings == []


def test_github_token_with_36_chars_detected_as_critical(tmp_path):
    token = "ghp_" + ("A" * 36)
    findings = for_rule(
        scan(tmp_path, {"app.py": f'github_token = "{token}"\n'}), "SECRET_GITHUB_TOKEN"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_github_token_with_35_chars_not_detected(tmp_path):
    token = "ghp_" + ("A" * 35)
    findings = for_rule(
        scan(tmp_path, {"app.py": f'github_token = "{token}"\n'}), "SECRET_GITHUB_TOKEN"
    )
    assert findings == []


def test_pem_private_key_banner_detected_as_critical(tmp_path):
    content = 'KEY = """\n-----BEGIN RSA PRIVATE KEY-----\nMIICdgIBADANBgkqhkiG9w0BAQEFAASC\n-----END RSA PRIVATE KEY-----\n"""\n'
    findings = for_rule(
        scan(tmp_path, {"app.py": content}), "SECRET_PRIVATE_KEY"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_public_key_banner_not_detected(tmp_path):
    content = 'KEY = """\n-----BEGIN PUBLIC KEY-----\nMIICIjANBgkqhkiG9w0BAQEFAAOC\n-----END PUBLIC KEY-----\n"""\n'
    findings = for_rule(scan(tmp_path, {"app.py": content}), "SECRET_PRIVATE_KEY")
    assert findings == []


def test_generic_api_key_with_high_entropy_detected_as_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": 'api_key = "aB3dE5gH7jK9mN1pQ"\n'}), "SECRET_GENERIC_API_KEY"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_generic_api_key_with_low_entropy_blocked_by_gate(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": 'api_key = "aaaaaaaaaaaaaaaa"\n'}), "SECRET_GENERIC_API_KEY"
    )
    assert findings == []


def test_db_url_with_credentials_detected_as_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": "DATABASE_URL = postgres://user:pass@host:5432/appdb\n"}),
        "SECRET_DB_URL",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_db_url_without_credentials_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": "DATABASE_URL = postgres://host:5432/appdb\n"}),
        "SECRET_DB_URL",
    )
    assert findings == []


def test_committed_env_file_detected_as_critical(tmp_path):
    findings = for_rule(
        scan(tmp_path, {".env": "DATABASE_URL=postgres://u:p@h/app\n"}), "SECRET_ENV_COMMITTED"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_env_example_file_not_treated_as_committed(tmp_path):
    findings = for_rule(
        scan(tmp_path, {".env.example": "DATABASE_URL=postgres://localhost/appdb\n"}),
        "SECRET_ENV_COMMITTED",
    )
    assert findings == []


def test_next_public_secret_detected_as_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {".env.local": "NEXT_PUBLIC_API_KEY=abc123\n"}), "SECRET_ENV_NEXT_PUBLIC"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_next_public_url_variable_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {".env.local": "NEXT_PUBLIC_API_URL=https://example.com\n"}),
        "SECRET_ENV_NEXT_PUBLIC",
    )
    assert findings == []


def test_stripe_live_key_detected_as_critical(tmp_path):
    key = "sk_live_" + ("a" * 24)
    findings = for_rule(
        scan(tmp_path, {"config.py": f'stripe_key = "{key}"\n'}), "SECRET_STRIPE"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_stripe_test_key_not_detected(tmp_path):
    key = "sk_test_" + ("a" * 24)
    findings = for_rule(
        scan(tmp_path, {"config.py": f'stripe_key = "{key}"\n'}), "SECRET_STRIPE"
    )
    assert findings == []


def test_eval_with_variable_arg_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": "result = eval(user_input)\n"}), "DANGER_EVAL"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_eval_with_literal_arg_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": 'result = eval("1 + 1")\n'}), "DANGER_EVAL"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_evaluate_call_not_detected_as_eval(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": "result = evaluate(expression)\n"}), "DANGER_EVAL"
    )
    assert findings == []


def test_child_process_with_variable_arg_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.js": "const out = child_process.execSync(cmd);\n"}),
        "DANGER_CHILD_PROCESS",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_child_process_with_literal_arg_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.js": 'child_process.execSync("ls -la")\n'}),
        "DANGER_CHILD_PROCESS",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_child_process_exec_file_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.js": 'child_process.execFile("ls", args)\n'}),
        "DANGER_CHILD_PROCESS",
    )
    assert findings == []


def test_innerhtml_detected_as_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.js": "el.innerHTML = userInput;\n"}), "DANGER_XSS_INNERHTML"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_textcontent_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.js": "el.textContent = userInput;\n"}), "DANGER_XSS_INNERHTML"
    )
    assert findings == []


def test_sql_concatenation_detected_as_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"app.py": 'query = "SELECT * FROM users WHERE id = " + user_id\n'}),
        "DANGER_SQL_CONCAT",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_sql_parameterized_query_not_detected(tmp_path):
    content = 'query = "SELECT * FROM users WHERE id = %s"\ncursor.execute(query, (user_id,))\n'
    findings = for_rule(
        scan(tmp_path, {"app.py": content}), "DANGER_SQL_CONCAT"
    )
    assert findings == []


def test_yaml_load_detected_as_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"load.py": "data = yaml.load(stream)\n"}), "DANGER_UNSAFE_YAML"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_yaml_safe_load_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"load.py": "data = yaml.safe_load(stream)\n"}), "DANGER_UNSAFE_YAML"
    )
    assert findings == []


def test_template_autoescape_off_detected_as_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"tpl.py": "env = Environment(autoescape=False)\n"}),
        "DANGER_TEMPLATE_ESCAPE_OFF",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_template_autoescape_on_not_detected(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"tpl.py": "env = Environment(autoescape=True)\n"}),
        "DANGER_TEMPLATE_ESCAPE_OFF",
    )
    assert findings == []


def test_cors_wildcard_with_credentials_high(tmp_path):
    content = 'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_CORS_CREDENTIALS"
    )
    assert severities(findings) == ["high", "high"]


def test_cors_wildcard_alone_medium(tmp_path):
    content = 'app.add_middleware(CORSMiddleware, allow_origins=["*"])\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_CORS_CREDENTIALS"
    )
    assert severities(findings) == ["high", "medium"]


def test_cors_specific_origins_not_detected(tmp_path):
    content = 'app.add_middleware(CORSMiddleware, allow_origins=["https://example.com"])\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_CORS_CREDENTIALS"
    )
    assert findings == []


def test_debug_true_detected_as_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"settings.py": "debug = True\n"}), "CONFIG_DEBUG_TRUE"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_debug_true_in_test_path_skipped(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"tests/test_settings.py": "debug = True\n"}), "CONFIG_DEBUG_TRUE"
    )
    assert findings == []


def test_secret_key_blocklist_value_high(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": 'SECRET_KEY = "changeme"\n'}), "CONFIG_HARDCODED_SECRET_KEY"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_secret_key_high_entropy_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": 'SECRET_KEY = "a8f9d3c2b1e4f5a6d7c8b9a0f1e2d3c4"\n'}),
        "CONFIG_HARDCODED_SECRET_KEY",
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_secret_key_from_environment_not_detected(tmp_path):
    content = 'SECRET_KEY = os.environ.get("SECRET_KEY")\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_HARDCODED_SECRET_KEY"
    )
    assert findings == []


def test_default_creds_pair_high(tmp_path):
    content = 'username = "admin"\npassword = "admin"\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_DEFAULT_CREDS"
    )
    assert findings
    assert set(severities(findings)) == {"high"}


def test_default_creds_single_pattern_medium(tmp_path):
    findings = for_rule(
        scan(tmp_path, {"config.py": 'username = "admin"\n'}), "CONFIG_DEFAULT_CREDS"
    )
    assert severities(findings) == ["high", "medium"]


def test_default_creds_strong_values_not_detected(tmp_path):
    content = 'username = "root"\npassword = "s3cret"\n'
    findings = for_rule(
        scan(tmp_path, {"config.py": content}), "CONFIG_DEFAULT_CREDS"
    )
    assert findings == []


def test_supabase_without_rls_policy_high(tmp_path):
    content = (
        "import { createClient } from '@supabase/supabase-js';\n"
        "export const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);\n"
    )
    findings = for_rule(
        scan(tmp_path, {"lib/supabase.ts": content}), "CONFIG_SUPABASE_NO_RLS"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_supabase_with_sql_rls_policy_not_detected(tmp_path):
    client = (
        "import { createClient } from '@supabase/supabase-js';\n"
        "export const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);\n"
    )
    rls = 'create policy "users_select" on users for select using (true);\n'
    findings = for_rule(
        scan(
            tmp_path,
            {"lib/supabase.ts": client, "migrations/0001.sql": rls},
        ),
        "CONFIG_SUPABASE_NO_RLS",
    )
    assert findings == []