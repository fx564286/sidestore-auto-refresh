"""V29: only safe typed login diagnostics; do not regress password/2FA handoff."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/templates/v3_headless_runtime.swift"
SERVICE = ROOT / "scripts/templates/v3_sidestore_service.swift"
BRIDGE = ROOT / "scripts/templates/v3_service_bridge.swift"

class V29AuthenticationFailureTraceTests(unittest.TestCase):
    def test_actual_signin_failure_cause_is_visible_without_raw_error(self):
        source = RUNTIME.read_text()
        self.assertIn("NRG_V29_SAFE_AUTH_CAUSE_V1", source)
        self.assertIn('let safeCause = v3SafeAuthCause(error)', source)
        self.assertIn('" [diagnostic: " + safeCause + ", code: "', source)
        self.assertIn('[V3_AUTH_CAUSE] stage=authentication', source)
        self.assertIn('[V3_AUTH_CAUSE] stage=provisioning', source)
        self.assertNotIn("error.localizedDescription", source)

    def test_infrastructure_source_families_are_typed_not_inferred(self):
        source = RUNTIME.read_text()
        start = source.index("func v3SafeAuthCause(_ error: Error) -> String")
        end = source.index("// MARK: - Provisioning failure guidance",start)
        diag = source[start:end]
        self.assertIn('error is SideSign.AnisetteError', diag)
        self.assertIn('error is V3SecretHandoffError', diag)
        self.assertIn('error as? DeveloperPortalError', diag)
        self.assertIn('case .authenticationHandshakeFailed: return "appleHandshake"', diag)
        self.assertIn('case .invalid2FAResponse: return "invalid2FAResponse"', diag)
        self.assertIn('case .unknown: return "portalUnknown"', diag)
        self.assertIn('error as? ServerError', diag)
        self.assertIn('return "unclassified"', diag)
        self.assertNotIn('String(describing: error)', diag)
        self.assertNotIn('error.localizedDescription', diag)

    def test_intermediate_prompt_error_gets_safe_diagnostics(self):
        source = RUNTIME.read_text()
        start = source.index("func handleSignInResult(")
        end = source.index("func resolveTeam(", start)
        segment = source[start:end]
        self.assertIn("NRG_V29_AUTH_PROMPT_ERROR_CAUSE_V2", segment)
        self.assertIn('wire["diagnosticCategory"] = category', segment)
        self.assertIn('wire["diagnosticCode"] = numericCode', segment)
        self.assertIn('v3SafeAuthCause(error)', segment)
        self.assertIn('v3SafeAuthNumericCode(error)', segment)
        self.assertIn('case .underlyingError(let code, _) = server', source)
        self.assertIn('stage=promptFailure', segment)
        self.assertNotIn('error.localizedDescription', segment)

    def test_terminal_failure_copies_existing_bounded_diagnostics(self):
        source = RUNTIME.read_text()
        start = source.index('let failure = CombinedFailure.capture(error, operation: "signIn", stage: .authentication, id: id)')
        end = source.index('func poll(id: String)', start)
        branch = source[start:end]
        self.assertIn("SCARLET_V113_TERMINAL_AUTH_DIAGNOSTICS", branch)
        self.assertIn('wire["diagnosticCategory"] = safeCause', branch)
        self.assertIn('wire["diagnosticCode"] = safeCode', branch)
        self.assertIn('wire["diagnosticType"] = safeType', branch)
        self.assertIn('let safeCode = v3SafeAuthNumericCode(error)', branch)
        self.assertIn('debugLog("[V3_AUTH_CAUSE] stage=authentication', branch)
        self.assertIn('code=\\(safeCode)', branch)
        self.assertIn('"failure": wire, "message": message', branch)
        self.assertNotIn('error.localizedDescription', branch)
        self.assertNotIn('String(describing: error)', branch)
        self.assertNotIn('wire["diagnosticResponseBody"]', branch)

    def test_prompt_diagnostic_category_is_bounded_and_visible(self):
        primitives = (ROOT / "scripts/templates/v3_behavioral_primitives.swift").read_text()
        shell = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        start = primitives.index("enum V3AuthFailureDiagnosticsPolicy")
        end = primitives.index("enum V3SignInFailureRoutingPolicy", start)
        segment = primitives[start:end]
        self.assertIn("knownDiagnosticCategories", segment)
        self.assertIn("category = failure", segment)
        self.assertIn("knownDiagnosticCategories.contains(category)", segment)
        self.assertIn("safePromptCause(failure)", segment)
        self.assertIn('case "unknown":\n', shell)
        self.assertIn("V3AuthFailureDiagnosticsPolicy.safePromptCause(failure)", shell)

    def test_auth_2fa_direct_payload_delivery_remains(self):
        service = SERVICE.read_text()
        bridge = BRIDGE.read_text()
        start = service.index('case "authRespond":')
        end = service.index('case "authCancel":',start)
        auth = service[start:end]
        self.assertIn('payload["answer"] as? [String: String]', auth)
        self.assertIn('auth.respond(id: target, promptID: promptID, answer: answer)',auth)
        self.assertNotIn('V3SecretStore.store',auth)
        self.assertIn('if !requestPayload.isEmpty { message["payload"] = requestPayload }',bridge)

if __name__ == "__main__":
    unittest.main()
