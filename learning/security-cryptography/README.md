# 보안·암호 기초: 신뢰 경계를 설계하고 검증하는 법

보안은 제품 끝에 붙이는 기능이 아니다. 누가 무엇을 믿고, 어떤 입력을 받아, 어느 경계를 통과시키며, 실패했을 때 무엇을 보존할지 정하는 설계 방법이다.

이 교재는 보안을 처음 보는 독자를 대상으로 한다. `키`, `nonce`, `인증서`, `RBAC`, `서명` 같은 낱말을 이미 안다고 가정하지 않는다. 각 장은 객체가 어디에 저장되는지, 누가 만들고 검사하는지, 입력이 어떤 중간 상태를 거쳐 결과가 되는지를 추적한다.

## 학습 목표

- 기밀성, 무결성, 인증, 인가, 가용성을 서로 구별한다.
- 위협 모델을 문장과 데이터 흐름 그림으로 작성한다.
- 해시, MAC, 전자서명, 암호화가 각각 해결하는 문제를 설명한다.
- AEAD nonce를 키의 수명 전체에서 유일하게 관리한다.
- 비밀번호와 복구 가능한 비밀 데이터를 서로 다른 방식으로 보관한다.
- TLS 1.3 연결에서 인증, 키 교환, 암호화가 맡는 일을 추적한다.
- Linux 격리와 Kubernetes RBAC의 경계를 과장하지 않는다.
- 공급망 서명, 감사 로그, 사고 대응의 증거 한계를 설명한다.

## 권장 학습 순서

| 단계 | 장 | 핵심 질문 |
|---|---|---|
| 지도 | [00](00-security-and-trust-map.md)–[02](02-identities-authentication-and-authorization.md) | 무엇을 누구에게서 보호하는가? |
| 암호 도구 | [03](03-randomness-keys-and-encoding.md)–[07](07-tls-key-exchange-and-certificates.md) | 각 도구가 정확히 무엇을 보장하는가? |
| 시스템 경계 | [08](08-linux-isolation-and-kubernetes-rbac.md)–[12](12-audit-logs-incidents-and-recovery.md) | 권한과 증거는 어디서 만들어지고 검사되는가? |
| 실험 | [13](13-local-models.md)–[15](15-exercises-glossary-and-sources.md) | 주장을 재현 가능한 실험으로 어떻게 바꾸는가? |

## 장 목록

1. [보안과 신뢰 지도](00-security-and-trust-map.md)
2. [위협 모델과 보안 목표](01-threat-models-and-security-goals.md)
3. [신원·인증·인가](02-identities-authentication-and-authorization.md)
4. [난수·키·인코딩](03-randomness-keys-and-encoding.md)
5. [해시·MAC·전자서명](04-hashes-macs-and-signatures.md)
6. [암호화·AEAD·nonce 수명](05-encryption-aead-and-nonce-lifetimes.md)
7. [비밀번호 저장과 비밀 관리](06-password-storage-and-secret-management.md)
8. [TLS 키 교환과 인증서](07-tls-key-exchange-and-certificates.md)
9. [Linux 격리와 Kubernetes RBAC](08-linux-isolation-and-kubernetes-rbac.md)
10. [네트워크 경계와 애플리케이션 보안](09-network-boundaries-and-application-security.md)
11. [공급망과 아티팩트 무결성](10-supply-chain-and-artifact-integrity.md)
12. [데이터 보호와 키 교체](11-data-protection-and-key-rotation.md)
13. [감사 로그·사고·복구](12-audit-logs-incidents-and-recovery.md)
14. [로컬 교육 모형](13-local-models.md)
15. [실험과 연구 방법](14-experiments-and-research.md)
16. [종합 문제·용어집·출처](15-exercises-glossary-and-sources.md)

## 그림과 실행 모형

- [그림 안내](assets/README.md): 신뢰 경계, 인증·인가, 암호 도구, nonce 수명, TLS, 사고 대응
- [실행 모형 안내](examples/README.md): 인가, nonce 등록부, 무결성 검증

실행 모형은 표준 라이브러리만 쓰며 고정 입력으로 동작한다. 실제 시스템을 스캔하거나 실제 암호 구현의 안전성을 인증하지 않는다.

## 읽을 때 지킬 구분

`공격자가 어렵게 느낄 것`은 보안 근거가 아니다. 보호 자산, 공격자 능력, 검증 규칙을 적어야 한다.

암호 알고리즘의 수학적 성질, 프로토콜의 보장, 제품의 설정은 서로 다른 층이다. 예를 들어 AES-GCM이 안전한 도구여도 nonce를 재사용한 운영은 안전하지 않다.

서명은 “서명한 바이트가 바뀌지 않았고 해당 키 소유자가 서명했다”는 증거다. 그 바이트가 취약점이나 악성 동작을 포함하지 않는다는 증거는 아니다.

## 대표 공식 자료

- [NIST SP 800-38D: GCM과 GMAC](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf)
- [RFC 8446: TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Kubernetes 인증](https://kubernetes.io/docs/reference/access-authn-authz/authentication/)
- [Kubernetes 인가](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)
- [Kubernetes Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)

---

[학습 자료 목차로 돌아가기](../README.md) · [다음: 보안과 신뢰 지도](00-security-and-trust-map.md)
