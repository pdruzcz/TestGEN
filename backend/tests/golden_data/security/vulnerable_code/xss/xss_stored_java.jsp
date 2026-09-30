<%-- Golden security fixture (Story 4.14) — stored XSS (CWE-79). --%>
<%-- Intentionally vulnerable reference sample for scanner regression tests. --%>
<%
    String comment = loadCommentFromDb();
    out.println("<div class=\"comment\">" + comment + "</div>");
%>
