# 01. 관계, SQL과 NULL

[이 책 목차](README.md) · [이전: 전체 지도](00-database-and-query-map.md) · [다음: Page, record와 buffer pool](02-pages-records-and-buffer-pools.md)

관계형 model은 row를 단순 spreadsheet 줄로만 보지 않는다. Attribute domain, key, predicate와 set/bag semantics를 구분해야 SQL의 NULL, join, aggregate 결과를 예측할 수 있다.

이 장의 SQL, page 수와 출력은 교육용 단순화이며 실제 PostgreSQL에서 실행한 결과가 아니다.

## 1. 먼저 알아야 할 단어

| 용어 | 뜻과 실제 위치 |
| --- | --- |
| Relation | 같은 attribute 구조를 가진 tuple 집합이라는 수학적 개념 |
| Table | DBMS가 relation을 구현하는 SQL object이며 duplicate row를 허용할 수 있음 |
| Tuple | Relation의 한 값 묶음이며 SQL에서는 row라고 부름 |
| Attribute | Tuple의 이름 있는 성분이며 SQL column에 대응 |
| Domain | Attribute가 가질 수 있는 값의 종류와 제약 |
| Primary key | Row identity를 나타내도록 선택한 unique·not-null key |
| Foreign key | 다른 table key를 참조하는 integrity constraint |
| NULL | 값이 없거나 알려지지 않았음을 나타내는 SQL marker |
| Predicate | Row가 조건을 만족하는지 계산하는 식 |
| Three-valued logic | SQL 조건 결과가 TRUE, FALSE, UNKNOWN인 논리 |

용어는 이름만 외우지 않고 어느 memory·file·catalog object에 존재하는지 연결한다.

## 2. 실제로 존재하는 객체

- Catalog의 table/column/type definition

- Table storage의 row version

- Unique index와 constraint metadata

- Query parse tree의 expression

- Executor filter node의 TRUE/FALSE/UNKNOWN 결과

객체마다 owner와 lifetime이 다르므로 SQL text와 storage byte를 같은 대상으로 보지 않는다.

## 3. 입력에서 결과까지

```mermaid
flowchart LR
    I["입력"] --> P["해석·계획"]
    P --> E["실행 주체"]
    E --> M["중간 상태"]
    M --> O["결과"]
```

1. DDL이 table 이름, column type와 constraint를 catalog에 만든다.

2. INSERT input이 type conversion과 constraint 검사를 받는다.

3. Row가 storage record로 encode된다.

4. SELECT parser가 column reference와 predicate를 만든다.

5. Binder가 column을 table attribute에 연결한다.

6. Executor가 row마다 predicate를 평가한다.

7. WHERE는 TRUE인 row만 통과시킨다.

8. ORDER BY가 필요하면 정렬 순서를 만든다.

9. Projection이 요청 column을 result row로 만든다.

10. Protocol serializer가 NULL marker와 값을 client로 보낸다.

## 4. 연결되는 숫자 예제

- employees 5 rows

- salary values: 100, 120, NULL, 80, NULL

- COUNT(*) = 5

- COUNT(salary) = 3

- AVG(salary) = (100+120+80)/3 = 100

숫자는 단위를 맞추고 어느 층의 추정값인지 표시해야 한다.

## 5. 왜 이 구조가 필요한가

SQL table은 duplicate row를 허용하는 bag semantics가 기본인 경우가 많다. DISTINCT가 중복 제거 작업을 추가한다.

NULL은 0이나 빈 문자열이 아니다. `salary = NULL`은 TRUE가 아니라 UNKNOWN이므로 `IS NULL`을 사용한다.

`NOT IN` subquery에 NULL이 있으면 비교가 UNKNOWN이 되어 예상과 다른 빈 결과가 나올 수 있다.

Primary key는 logical identity이고 physical row address가 아니다. Update·vacuum·rewrite로 위치가 바뀔 수 있다.

Foreign key는 참조 무결성을 돕지만 distributed service 사이 business consistency를 자동 해결하지 않는다.

Collation은 text 비교·정렬 규칙이며 byte order와 같지 않을 수 있다.

## 6. 실행 중 관찰 질문

- 입력 row 수와 출력 row 수는 각각 얼마인가?

- Memory object와 durable file object는 무엇인가?

- 어느 component가 다음 상태를 만들었는가?

- 추정치와 실제 측정치를 섞지 않았는가?

- Failure 뒤 재시도하면 side effect가 중복되는가?

- Cache가 차가울 때와 따뜻할 때 결과가 달라지는가?

## 7. 흔한 오해와 반례

- 오해: Relation과 physical file은 같은 object다.

- 오해: NULL은 모든 비교에서 다른 값보다 작다.

- 오해: COUNT(column)은 row 수와 항상 같다.

- 오해: Primary key 순서대로 table file이 저장된다.

- 오해: Foreign key가 있으면 join이 자동으로 빠르다.

반례는 구현이 틀렸다는 뜻보다 적용 조건이 빠졌음을 보여 준다.

## 8. 작은 설계 점검

1. Logical object와 physical object를 각각 적는다.

2. Read path와 write path를 따로 그린다.

3. Memory에서만 끝난 상태와 durable 상태를 구분한다.

4. Concurrent transaction 또는 worker가 끼어드는 지점을 찾는다.

5. Cost를 row, page, byte, network 단위로 손계산한다.

6. 공식 문서의 보장과 교육용 가정을 구분한다.

## 9. 문제

1. `WHERE x <> 5`가 NULL row를 반환하는가?

2. 5개 row 중 column 값 두 개가 NULL이면 COUNT(*)와 COUNT(column)은?

3. Primary key와 index는 같은 개념인가?

## 10. 해설

1. 아니다. NULL과 5의 비교는 UNKNOWN이며 WHERE는 TRUE만 통과시킨다.

2. 각각 5와 3이다.

3. 아니다. Key는 logical constraint이고 index는 이를 구현하거나 query를 빠르게 할 수 있는 physical structure다.

## 11. 공식 자료

- [PostgreSQL current documentation](https://www.postgresql.org/docs/current/)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 장의 logical object가 더 구체적인 storage 또는 execution state로 바뀌는 과정을 이어서 본다.


## 보강: 논리 행과 저장 레코드를 구별하기

Relation은 같은 속성 구조를 가진 tuple의 집합이라는 논리 모델이다. SQL table은 이름, column type, constraint를 가진 데이터베이스 객체이며 내부 저장 순서 자체가 관계의 의미는 아니다. Row는 질의 결과의 논리 행이고 record는 페이지 안의 바이트 표현이다. `ORDER BY`가 없다면 물리 레코드 순서가 결과 순서를 보장하지 않는다.

NULL은 0이나 빈 문자열이 아니라 “알 수 없거나 적용되지 않는 값” 표지다. `NULL = NULL`은 TRUE가 아니라 UNKNOWN이고 WHERE는 TRUE인 행만 남긴다. 따라서 `discount <> 0`도 NULL discount 행을 남기지 않는다. 포함하려면 `discount IS NULL OR discount <> 0`처럼 업무 의미를 명시해야 한다.
