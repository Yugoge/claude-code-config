---
description: Security vulnerability analysis and recommendations
argument-hint: [file-path-or-directory]
allowed-tools: [Read, Grep, Glob, Bash]
---

# Security Vulnerability Check

Perform security analysis on $ARGUMENTS to identify potential vulnerabilities.

## Security Checklist

### 🔴 Critical Vulnerabilities

#### 1. Injection Attacks
- SQL Injection
- Command Injection
- LDAP Injection
- XML/XPath Injection
- Template Injection

#### 2. Authentication & Authorization
- Weak password policies
- Missing authentication
- Broken access control
- Session management issues
- JWT vulnerabilities

#### 3. Sensitive Data Exposure
- Hardcoded credentials (API keys, passwords, tokens)
- Unencrypted sensitive data
- Weak encryption algorithms
- Data leakage in logs/errors

#### 4. XSS (Cross-Site Scripting)
- Reflected XSS
- Stored XSS
- DOM-based XSS
- Unsafe HTML rendering

### 🟡 Important Issues

#### 5. CSRF (Cross-Site Request Forgery)
- Missing CSRF tokens
- Unsafe state-changing operations

#### 6. Security Misconfiguration
- Default credentials
- Unnecessary features enabled
- Insecure defaults
- Verbose error messages

#### 7. Insecure Dependencies
- Outdated libraries with known vulnerabilities
- Packages with security advisories

#### 8. Insufficient Logging
- Security events not logged
- Sensitive data in logs
- Log injection vulnerabilities

### 🟢 Best Practices

#### 9. Input Validation
- Whitelist validation
- Type checking
- Length limits
- Format validation

#### 10. Secure Communication
- HTTPS enforcement
- Certificate validation
- Secure protocols (TLS 1.2+)

## Output Format

For each finding:
1. **Severity**: Critical / High / Medium / Low
2. **Type**: Category of vulnerability
3. **Location**: File and line number
4. **Description**: What the vulnerability is
5. **Exploit Scenario**: How it could be exploited
6. **Recommendation**: How to fix it
7. **Code Example**: Secure implementation

Prioritize by severity and provide actionable fixes.
