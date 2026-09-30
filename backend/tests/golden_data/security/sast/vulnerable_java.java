// Golden SAST sample (Java) — known-vulnerable, Epic 4 Story 4.1.
// Intentionally insecure reference code used to freeze SAST detection output.
// DO NOT use any of this in production. Each flagged line is annotated.

import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.Statement;

public class VulnerableJava {

    // hardcoded_secret (CWE-798)
    private static final String PASSWORD = "SuperSecret123!";

    public void query(Connection conn, String userId) throws Exception {
        Statement st = conn.createStatement();
        // sql_injection (CWE-89) — string concatenation in query
        st.executeQuery("SELECT * FROM accounts WHERE id = '" + userId + "'");
    }

    public byte[] weakHash(byte[] data) throws Exception {
        // weak_cryptography (CWE-327) — MD5
        MessageDigest md = MessageDigest.getInstance("MD5");
        return md.digest(data);
    }
}
