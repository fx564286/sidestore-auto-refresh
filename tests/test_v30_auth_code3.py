"""V30 Apple sign-in code 3: classify error's Swift type/case, not the integer.

The pinned AnisetteKit has a distinct AnisetteError.readFailure that can
bridge to 3; a numeric code alone must not trigger data resets or false claims.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class V30AuthCode3Tests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "scripts/templates/v3_headless_runtime.swift").read_text()
        self.primitives = (ROOT / "scripts/templates/v3_behavioral_primitives.swift").read_text()
        self.shell = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()

    def test_adi_read_has_typed_proof(self):
        self.assertIn("import AnisetteKit", self.runtime)
        self.assertIn("NRG_V30_TYPED_AUTH_ORIGIN_V1", self.runtime)
        self.assertIn("error as? AnisetteKit.AnisetteError", self.runtime)
        self.assertIn('case .readFailure: return "onDeviceAnisetteRead"', self.runtime)
        self.assertIn('case .librariesNotFound: return "onDeviceAnisetteLibraries"', self.runtime)
        self.assertIn('case .adiError: return "onDeviceAnisetteNative"', self.runtime)
        self.assertIn('case .httpError: return "onDeviceAnisetteHTTP"', self.runtime)

    def test_code3_is_not_interpreted_without_type(self):
        start=self.runtime.index("func v3SafeAuthCause(")
        end=self.runtime.index("// SideSign ServerError.underlyingError",start)
        cause=self.runtime[start:end]
        self.assertNotIn("if (error as NSError).code == 3",cause)
        self.assertNotIn("case 3:",cause)
        self.assertNotIn("error.localizedDescription",cause)

    def test_distinguish_sidestore_account_from_anisette(self):
        self.assertIn("error as? OperationError",self.runtime)
        self.assertIn('case .notAuthenticated: return "sideStoreAccountState"',self.runtime)
        self.assertIn('case .missingAppGroup: return "sideStoreAppGroup"',self.runtime)
        self.assertIn('if let wrapped = error as? ALTWrappedError',self.runtime)

    def test_native_adi_http_code_visible_without_payload(self):
        a=self.runtime.index("func v3SafeAuthNumericCode(")
        b=self.runtime.index("// MARK:",a)
        code=self.runtime[a:b]
        self.assertIn("case .httpError(let statusCode, _): return statusCode",code)
        self.assertIn("case .adiError(let code, _): return Int(code)",code)
        self.assertNotIn("description",code)
        self.assertNotIn("message",code)

    def test_error_type_is_bounded_and_never_serializes_error_payload(self):
        runtime=self.runtime
        self.assertIn("func v3SafeAuthTypeID(_ error: Error, depth: Int = 0)",runtime)
        self.assertIn("String(reflecting: type(of: error))",runtime)
        self.assertIn("name.utf8.count <= 96",runtime)
        self.assertIn("wire[\"diagnosticType\"] = v3SafeAuthTypeID(error)",runtime)
        self.assertIn("rawType.utf8.count <= 96",self.primitives)
        self.assertIn('", type: " + safeType + "]"',runtime)
        self.assertNotIn("String(describing: error)",runtime[runtime.index("func v3SafeAuthTypeID"):runtime.index("// SideSign ServerError.underlyingError")])

    def test_prompt_screen_allows_only_fixed_type_tokens(self):
        categories = ["onDeviceAnisetteRead","onDeviceAnisetteNative","sideStoreAccountState","sideStoreAppGroup"]
        for category in categories:self.assertIn('"'+category+'"',self.primitives)
        self.assertIn("knownDiagnosticCategories.contains(category)",self.primitives)
        self.assertIn("V3AuthFailureDiagnosticsPolicy.safePromptCause(failure)",self.shell)

if __name__ == "__main__":unittest.main()
