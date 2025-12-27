---
description: Security vulnerability analysis and recommendations
argument-hint: [file-path-or-directory]
allowed-tools: [Read, Grep, Glob, Bash]
---

# Security Vulnerability Check | 安全漏洞检查

Perform security analysis on $ARGUMENTS to identify potential vulnerabilities.

## Security Checklist | 安全检查清单

### 🔴 Critical Vulnerabilities | 严重漏洞

#### 1. Injection Attacks | 注入攻击
- SQL Injection
- Command Injection
- LDAP Injection
- XML/XPath Injection
- Template Injection

#### 2. Authentication & Authorization | 认证与授权
- Weak password policies
- Missing authentication
- Broken access control
- Session management issues
- JWT vulnerabilities

#### 3. Sensitive Data Exposure | 敏感数据暴露
- Hardcoded credentials (API keys, passwords, tokens)
- Unencrypted sensitive data
- Weak encryption algorithms
- Data leakage in logs/errors

#### 4. XSS (Cross-Site Scripting) | 跨站脚本
- Reflected XSS
- Stored XSS
- DOM-based XSS
- Unsafe HTML rendering

### 🟡 Important Issues | 重要问题

#### 5. CSRF (Cross-Site Request Forgery) | 跨站请求伪造
- Missing CSRF tokens
- Unsafe state-changing operations

#### 6. Security Misconfiguration | 安全配置错误
- Default credentials
- Unnecessary features enabled
- Insecure defaults
- Verbose error messages

#### 7. Insecure Dependencies | 不安全的依赖
- Outdated libraries with known vulnerabilities
- Packages with security advisories

#### 8. Insufficient Logging | 日志不足
- Security events not logged
- Sensitive data in logs
- Log injection vulnerabilities

### 🟢 Best Practices | 最佳实践

#### 9. Input Validation | 输入验证
- Whitelist validation
- Type checking
- Length limits
- Format validation

#### 10. Secure Communication | 安全通信
- HTTPS enforcement
- Certificate validation
- Secure protocols (TLS 1.2+)

## Output Format | 输出格式

For each finding:
1. **Severity**: Critical / High / Medium / Low
2. **Type**: Category of vulnerability
3. **Location**: File and line number
4. **Description**: What the vulnerability is
5. **Exploit Scenario**: How it could be exploited
6. **Recommendation**: How to fix it
7. **Code Example**: Secure implementation

Prioritize by severity and provide actionable fixes.
