# slab-design-real_v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained, runnable Spring Boot application at `sample-repos/slab-design-real_v2/` that exposes the 21-step slab design algorithm via REST API with H2 in-memory DB, 5 golden test scenarios, and step-by-step trace responses for simulation verification.

**Architecture:** Maven 4-module multi-module (boot → facade → feature → store) mirroring v1. Replace Oracle/Kafka/MyBatis with H2 + JPA. Copy v1 algorithm code with surgical drama-DNA cleanup (preserve algorithm output). Add per-step `TraceCollector` decorator. 10 REST endpoints + Swagger UI. 3-tier tests (action unit + repo + scenario golden).

**Tech Stack:** Java 21, Spring Boot 3.4.0, Spring Data JPA, H2 (Oracle compat mode), springdoc-openapi 2.6.0, JUnit 5, Mockito, AssertJ, RestAssured 5.

**References:**
- Spec: `sample-repos/slab-design-real_v2/docs/SPEC.md`
- v1 (READ-ONLY): `sample-repos/slab-design-real/`

**Constraints:**
- All artifacts under `sample-repos/slab-design-real_v2/` only
- v1 (`sample-repos/slab-design-real/`) and other onTong areas (backend/, frontend/, data/, scripts/, toClaude/<section>/) are READ-ONLY
- Algorithm output identical to v1 (only drama-DNA cleanup permitted)

---

## Conventions

- `V1` = `sample-repos/slab-design-real`
- `V2` = `sample-repos/slab-design-real_v2`
- All commands run from `/Users/donghae/workspace/ai/onTong`
- Commit messages use conventional commits (`feat:`, `chore:`, `test:`, `docs:`)
- Each task ends with `git add` + `git commit`. The user will decide when/whether to push.
- Java package convention identical to v1: `com.example.slabdesign.{boot,facade,feature,store}.*`
- Drama DNA cleanup table is in `SPEC.md` §7. Cleanup is allowed; algorithm output must remain identical.

---

## Phase 1 — Project Bootstrap

### Task 1.1: Create directory skeleton

**Files:**
- Create dir: `V2/slab-design-{boot,facade,feature,store}/src/{main,test}/java`
- Create dir: `V2/slab-design-boot/src/main/resources/db/seed`
- Create dir: `V2/slab-design-boot/src/test/resources/golden`
- Create dir: `V2/.mvn/wrapper`
- Create: `V2/.gitignore`
- Copy from v1: `mvnw`, `mvnw.cmd`, `.mvn/wrapper/maven-wrapper.properties` (if exists in v1)

- [ ] **Step 1: Create directories**

Run:
```bash
cd /Users/donghae/workspace/ai/onTong
V2=sample-repos/slab-design-real_v2
mkdir -p $V2/slab-design-boot/src/main/java/com/example/slabdesign/boot/config
mkdir -p $V2/slab-design-boot/src/main/resources/db/seed
mkdir -p $V2/slab-design-boot/src/test/java/com/example/slabdesign/boot/integration
mkdir -p $V2/slab-design-boot/src/test/resources/golden
mkdir -p $V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/{working,orders,results,history,seed}
mkdir -p $V2/slab-design-facade/src/test/java/com/example/slabdesign/facade
mkdir -p $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/{designer,driver,trace,common}
mkdir -p $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/{action,wrapper,service}
mkdir -p $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/{service,wrapper}
mkdir -p $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/history/{action,service,wrapper}
mkdir -p $V2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/process/working/action
mkdir -p $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/{std,working,history}
mkdir -p $V2/slab-design-store/src/test/java/com/example/slabdesign/store
mkdir -p $V2/.mvn/wrapper
```

- [ ] **Step 2: Copy Maven Wrapper from v1**

Run:
```bash
cp sample-repos/slab-design-real/mvnw sample-repos/slab-design-real_v2/mvnw
cp sample-repos/slab-design-real/mvnw.cmd sample-repos/slab-design-real_v2/mvnw.cmd
cp sample-repos/slab-design-real/mvnwDebug sample-repos/slab-design-real_v2/mvnwDebug 2>/dev/null || true
cp sample-repos/slab-design-real/mvnwDebug.cmd sample-repos/slab-design-real_v2/mvnwDebug.cmd 2>/dev/null || true
chmod +x sample-repos/slab-design-real_v2/mvnw
[ -f sample-repos/slab-design-real/.mvn/wrapper/maven-wrapper.properties ] && cp sample-repos/slab-design-real/.mvn/wrapper/maven-wrapper.properties sample-repos/slab-design-real_v2/.mvn/wrapper/maven-wrapper.properties || echo "no maven-wrapper.properties in v1, will rely on mvnw script defaults"
```

- [ ] **Step 3: Create `.gitignore`**

Write to `sample-repos/slab-design-real_v2/.gitignore`:
```
target/
.idea/
*.iml
.DS_Store
.vscode/
.classpath
.project
.settings/
HELP.md
*.log
```

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "chore(slab-v2): bootstrap directory skeleton + maven wrapper"
```

---

### Task 1.2: Parent `pom.xml`

**Files:**
- Create: `V2/pom.xml`

- [ ] **Step 1: Write parent pom**

Write to `sample-repos/slab-design-real_v2/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.4.0</version>
        <relativePath/>
    </parent>

    <groupId>com.example.slabdesign</groupId>
    <artifactId>slab-design-v2</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>pom</packaging>
    <name>slab-design-v2</name>
    <description>slab-design runnable v2 — H2 + 5 golden scenarios + step trace</description>

    <modules>
        <module>slab-design-boot</module>
        <module>slab-design-facade</module>
        <module>slab-design-feature</module>
        <module>slab-design-store</module>
    </modules>

    <properties>
        <java.version>21</java.version>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <springdoc.version>2.6.0</springdoc.version>
        <restassured.version>5.5.0</restassured.version>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>com.example.slabdesign</groupId>
                <artifactId>slab-design-store</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.example.slabdesign</groupId>
                <artifactId>slab-design-feature</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.example.slabdesign</groupId>
                <artifactId>slab-design-facade</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>org.springdoc</groupId>
                <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
                <version>${springdoc.version}</version>
            </dependency>
            <dependency>
                <groupId>io.rest-assured</groupId>
                <artifactId>rest-assured</artifactId>
                <version>${restassured.version}</version>
                <scope>test</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

- [ ] **Step 2: Commit**

```bash
git add sample-repos/slab-design-real_v2/pom.xml
git commit -m "chore(slab-v2): parent pom (spring-boot 3.4, java 21, h2, springdoc, restassured)"
```

---

### Task 1.3: Module pom.xml files

**Files:**
- Create: `V2/slab-design-store/pom.xml`
- Create: `V2/slab-design-feature/pom.xml`
- Create: `V2/slab-design-facade/pom.xml`
- Create: `V2/slab-design-boot/pom.xml`

- [ ] **Step 1: store/pom.xml**

Write to `V2/slab-design-store/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.example.slabdesign</groupId>
        <artifactId>slab-design-v2</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>
    <artifactId>slab-design-store</artifactId>
    <name>slab-design-store</name>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: feature/pom.xml**

Write to `V2/slab-design-feature/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.example.slabdesign</groupId>
        <artifactId>slab-design-v2</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>
    <artifactId>slab-design-feature</artifactId>
    <name>slab-design-feature</name>
    <dependencies>
        <dependency>
            <groupId>com.example.slabdesign</groupId>
            <artifactId>slab-design-store</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 3: facade/pom.xml**

Write to `V2/slab-design-facade/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.example.slabdesign</groupId>
        <artifactId>slab-design-v2</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>
    <artifactId>slab-design-facade</artifactId>
    <name>slab-design-facade</name>
    <dependencies>
        <dependency>
            <groupId>com.example.slabdesign</groupId>
            <artifactId>slab-design-feature</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 4: boot/pom.xml**

Write to `V2/slab-design-boot/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.example.slabdesign</groupId>
        <artifactId>slab-design-v2</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>
    <artifactId>slab-design-boot</artifactId>
    <name>slab-design-boot</name>
    <dependencies>
        <dependency>
            <groupId>com.example.slabdesign</groupId>
            <artifactId>slab-design-facade</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <mainClass>com.example.slabdesign.boot.SlabDesignApplication</mainClass>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-{store,feature,facade,boot}/pom.xml
git commit -m "chore(slab-v2): module poms with explicit deps (no kafka, no mybatis, no oracle)"
```

---

### Task 1.4: Application entry + minimal config + smoke test

**Files:**
- Create: `V2/slab-design-boot/src/main/java/com/example/slabdesign/boot/SlabDesignApplication.java`
- Create: `V2/slab-design-boot/src/main/resources/application.yml`
- Create: `V2/slab-design-boot/src/test/java/com/example/slabdesign/boot/SmokeTest.java`

- [ ] **Step 1: Write `SlabDesignApplication.java`**

Write to `V2/slab-design-boot/src/main/java/com/example/slabdesign/boot/SlabDesignApplication.java`:
```java
package com.example.slabdesign.boot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@SpringBootApplication
@ComponentScan(basePackages = "com.example.slabdesign")
@EntityScan(basePackages = "com.example.slabdesign.store")
@EnableJpaRepositories(basePackages = "com.example.slabdesign.store")
public class SlabDesignApplication {
    public static void main(String[] args) {
        SpringApplication.run(SlabDesignApplication.class, args);
    }
}
```

- [ ] **Step 2: Write `application.yml`**

Write to `V2/slab-design-boot/src/main/resources/application.yml`:
```yaml
spring:
  application:
    name: slab-design-real-v2
  datasource:
    url: jdbc:h2:mem:slabdesign;MODE=Oracle;DB_CLOSE_DELAY=-1
    driver-class-name: org.h2.Driver
    username: sa
    password:
  jpa:
    database-platform: org.hibernate.dialect.H2Dialect
    hibernate:
      ddl-auto: create-drop
    show-sql: false
    open-in-view: false
    defer-datasource-initialization: true
  sql:
    init:
      mode: always
      data-locations:
        - classpath:db/seed/01_master.sql
        - classpath:db/seed/02_orders.sql
      continue-on-error: false
  h2:
    console:
      enabled: true
      path: /h2-console

springdoc:
  api-docs:
    path: /v3/api-docs
  swagger-ui:
    path: /swagger-ui.html

server:
  port: 8080

logging:
  level:
    com.example.slabdesign: DEBUG
    org.hibernate.SQL: WARN
    org.springframework.boot.autoconfigure: INFO
```

- [ ] **Step 3: Write empty seed files (will populate later)**

Write to `V2/slab-design-boot/src/main/resources/db/seed/01_master.sql`:
```sql
-- master tables seed (populated in Phase 10)
-- intentionally empty for now
```

Write to `V2/slab-design-boot/src/main/resources/db/seed/02_orders.sql`:
```sql
-- order tables seed (populated in Phase 10)
-- intentionally empty for now
```

- [ ] **Step 4: Write `SmokeTest.java`**

Write to `V2/slab-design-boot/src/test/java/com/example/slabdesign/boot/SmokeTest.java`:
```java
package com.example.slabdesign.boot;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class SmokeTest {
    @Test
    void contextLoads() {
        // intentionally empty: passes if Spring context starts
    }
}
```

- [ ] **Step 5: Run build to verify**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw clean test
```

Expected: BUILD SUCCESS, SmokeTest passes (no entities yet, ddl-auto creates empty schema, both seed SQL files run without error).

- [ ] **Step 6: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "feat(slab-v2): app entry + h2 application.yml + smoke test"
```

---

## Phase 2 — Store Module (Entities, JPOs, Repos)

This phase mostly copies from v1 with these blanket transformations applied to every Java file:

**Blanket renames (applied via Edit on each file after copy):**
- Package `com.example.slabdesign.store.sd.std.oracle.*` → `com.example.slabdesign.store.sd.std.*` (drop `oracle` segment)
- Package `com.example.slabdesign.store.sd.working.oracle.*` → `com.example.slabdesign.store.sd.working.*`
- Package `com.example.slabdesign.store.sd.history.oracle.*` → `com.example.slabdesign.store.sd.history.*`
- Folder names follow: `store/sd/std/oracle/{jpo,repository}` → `store/sd/std/{jpo,repository}`

**Drama DNA cleanup applied to copied entities/JPOs:**
- `@Column(name = "PRODUCT_TYPE_CD")` → `@Column(name = "PRODUCT_CD")`
- `@Column(name = "PRODUCT_NAME_CD")` → `@Column(name = "PRODUCT_CD")`
- `@Column(name = "PRODUCT_KIND_CD")` → `@Column(name = "PRODUCT_CD")`
- Java field `productTypeCd`, `productNameCd`, `productKindCd` → `productCd`
- Remove `@author 김XX (YYYY-MM-DD)` style javadoc
- Remove commented-out blocks
- Keep all other fields and structure as-is

### Task 2.1: Copy std (master) layer (8 entity sets)

**Files (per entity set: Entity + Jpo + PK + Repository):** 8 sets
- CastSpec, CustomerStd, EdgingGroup, EdgingSpec, HrMaxWgt, HrMinWgt, HrSpec, SdProductivityStd
- Plus logic classes (CastSpecLogic, etc.) where they exist in v1

Source paths (v1):
```
slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/
├── domain/entity/*.java        (8 entities)
├── domain/logic/*.java         (8 logics)
├── oracle/jpo/*.java           (8 JPOs + 8 PKs)
└── oracle/repository/*.java    (8 repositories)
```

Destination paths (v2):
```
slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/
├── domain/entity/*.java
├── domain/logic/*.java
├── jpo/*.java                  (oracle/ segment dropped)
└── repository/*.java
```

- [ ] **Step 1: Copy entire std directory tree, then move oracle/ subdirs up one level**

```bash
cd /Users/donghae/workspace/ai/onTong
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/. \
      $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/jpo \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/jpo
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/repository \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/repository
rmdir $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle
```

- [ ] **Step 2: Update package declarations + imports for moved files**

Apply Edit on each file under v2 std/jpo and std/repository:
- `package com.example.slabdesign.store.sd.std.oracle.jpo;` → `package com.example.slabdesign.store.sd.std.jpo;`
- `package com.example.slabdesign.store.sd.std.oracle.repository;` → `package com.example.slabdesign.store.sd.std.repository;`
- `import com.example.slabdesign.store.sd.std.oracle.jpo.` → `import com.example.slabdesign.store.sd.std.jpo.`
- `import com.example.slabdesign.store.sd.std.oracle.repository.` → `import com.example.slabdesign.store.sd.std.repository.`

Use grep to find every reference and Edit to apply each replacement. Files are static (PK + Jpo + Repository), so the rename can be done by reading each file once.

- [ ] **Step 3: Apply drama-DNA cleanup pass**

For each entity / JPO file under v2/store/sd/std/, apply Edit:
- `PRODUCT_TYPE_CD` → `PRODUCT_CD`
- `PRODUCT_NAME_CD` → `PRODUCT_CD`
- `PRODUCT_KIND_CD` → `PRODUCT_CD`
- `productTypeCd` → `productCd`
- `productNameCd` → `productCd`
- `productKindCd` → `productCd`

Note: After all renames, getters/setters/usages all read `productCd`.

Also remove any `// @author 김... (YYYY-MM-DD)` lines.

- [ ] **Step 4: Verify compile**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw -pl slab-design-store compile -am
```
Expected: BUILD SUCCESS.

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-store/
git commit -m "feat(slab-v2/store): copy std layer (8 master tables) with PRODUCT_CD unification"
```

---

### Task 2.2: Copy working layer (4 ORDER tables + SLAB_RESULT)

Source paths (v1):
```
slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/
├── domain/entity/SDOrderEntity.java, SDSlabEntity.java
├── domain/logic/SDOrderLogic.java, SDSlabLogic.java
└── oracle/{jpo,repository}/*.java
```

Destination (v2): same with `oracle/` segment dropped.

- [ ] **Step 1: Copy directory + move oracle subdirs up**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/. \
      $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/oracle/jpo \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/jpo
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/oracle/repository \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/repository
rmdir $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/oracle
```

- [ ] **Step 2: Update package declarations + imports (working oracle → working)**

Same pattern as Task 2.1 Step 2 but for the `working` subtree.

- [ ] **Step 3: Apply PRODUCT_CD cleanup**

Same column / field rename pass on every file under `v2/store/sd/working/`.

- [ ] **Step 4: Replace SDOrderLogic reflection mapping with explicit mapper**

Read v1 file `slab-design-store/.../working/domain/logic/SDOrderLogic.java`. It uses `Field.get`/`Field.set` reflection to copy between JPOs and `SDOrderEntity`.

Replace the reflection block with explicit field-by-field assignment. The structure of the new method body must mirror the field set defined in `SDOrderEntity` and the source JPOs (`SDOrderOsJpo`, `SDOrderOmJpo`, `SDOrderQdJpo`, `SDOrderChemicalJpo`).

After cleanup, the file should contain a method like:
```java
public static SDOrderEntity from(SDOrderOsJpo os, SDOrderOmJpo om, SDOrderQdJpo qd, SDOrderChemicalJpo chem) {
    SDOrderEntity entity = new SDOrderEntity();
    entity.setCmpCd(os.getCmpCd());
    entity.setOrgCd(os.getOrgCd());
    entity.setOrderNo(os.getOrderNo());
    // ... all fields explicitly. Use the original SDOrderEntity field list as the source of truth.
    return entity;
}
```

If a field in v1 was set via `field.set(...)` against private fields, switch to setters (add public setters in entity if missing).

- [ ] **Step 5: Verify compile**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw -pl slab-design-store compile -am
```

- [ ] **Step 6: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/working/
git commit -m "feat(slab-v2/store): copy working layer + replace SDOrderLogic reflection with explicit mapper"
```

---

### Task 2.3: Copy history layer

- [ ] **Step 1: Copy + move oracle/ up**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/. \
      $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/oracle/jpo \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/jpo
mv $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/oracle/repository \
   $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/repository
rmdir $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/oracle
```

- [ ] **Step 2: Package + import updates**

Apply same pattern as Task 2.1 for `history` subtree.

- [ ] **Step 3: Verify compile**

```bash
./mvnw -pl slab-design-store compile -am
```
Expected: BUILD SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/history/
git commit -m "feat(slab-v2/store): copy history layer (SLAB_DESIGN_HIST)"
```

---

### Task 2.4: Copy analysis stub + remove unused

`SdAnalysisEntity` is referenced from `SdAnalysisAction` (placeholder). Copy as-is for now; the controller will be wired in Phase 8.

- [ ] **Step 1: Copy analysis dir**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-store/src/main/java/com/example/slabdesign/store/sd/analysis/. \
      $V2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/analysis/
```

- [ ] **Step 2: Verify compile**

```bash
./mvnw -pl slab-design-store compile -am
```

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/analysis/
git commit -m "feat(slab-v2/store): copy analysis placeholder"
```

---

### Task 2.5: Repository smoke test (`@DataJpaTest` baseline)

**Files:**
- Create: `V2/slab-design-store/src/test/java/com/example/slabdesign/store/RepositoryContextTest.java`

- [ ] **Step 1: Write minimal `@DataJpaTest`**

Write to `V2/slab-design-store/src/test/java/com/example/slabdesign/store/RepositoryContextTest.java`:
```java
package com.example.slabdesign.store;

import com.example.slabdesign.store.sd.std.repository.CastSpecRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase
class RepositoryContextTest {

    @Autowired CastSpecRepository castSpecRepository;

    @Test
    void allRepositoriesWired_emptyDbReturnsEmpty() {
        assertThat(castSpecRepository.count()).isZero();
    }
}
```

- [ ] **Step 2: Run test**

```bash
./mvnw -pl slab-design-store test
```
Expected: PASS. This proves all 12 tables generate via `ddl-auto: create-drop` and a sample repository wires.

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-store/src/test/
git commit -m "test(slab-v2/store): repository wiring smoke test"
```

---

## Phase 3 — Feature Module Wrappers + Constants

### Task 3.1: Copy working/wrapper/

Source (v1):
```
slab-design-feature/.../sd/process/working/wrapper/
├── AlgorithmException.java
├── ProductCategory.java
├── SdErrorCode.java
├── SdWorkingRequest.java
├── SdWorkingResponse.java
└── ValidationResult.java
```

- [ ] **Step 1: Copy wrapper dir**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/wrapper/. \
      $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/wrapper/
```

- [ ] **Step 2: Compile check**

```bash
./mvnw -pl slab-design-feature compile -am
```
(May fail until Task 3.2 since productCd renames cascade.)

- [ ] **Step 3: Apply PRODUCT_CD field renames in wrapper files (if any reference)**

Run grep to find references:
```bash
grep -rn "productTypeCd\|productNameCd\|productKindCd" sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/wrapper/
```
Apply `productCd` rename on any matches.

- [ ] **Step 4: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/wrapper/
git commit -m "feat(slab-v2/feature): copy working/wrapper (DTOs + error codes)"
```

---

### Task 3.2: Create `SdConstants.java`

Read v1 source files to find magic numbers:
```bash
grep -rn "999999\|0\.95\|7\.82\|0\.86" sample-repos/slab-design-real/slab-design-feature/src/main/java/
```
Identify the meaningful constants and extract.

**Files:**
- Create: `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/common/SdConstants.java`

- [ ] **Step 1: Write SdConstants.java**

Write to `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/common/SdConstants.java`:
```java
package com.example.slabdesign.feature.sd.common;

/**
 * Slab design algorithm constants extracted from v1's drama-DNA magic numbers.
 * Numerical values are identical to v1 to preserve algorithm output.
 */
public final class SdConstants {

    /** Default cumulative productivity multiplier when productivity_std lookup misses. */
    public static final double DEFAULT_PRODUCTIVITY = 0.95;

    /** Default specific gravity (강종별 분기 자리만 마련, 현재 상수). */
    public static final double DEFAULT_SPECIFIC_GRAVITY = 7.82;

    /** Sentinel "no upper bound" value used in width / length / weight ranges. */
    public static final double NO_UPPER_BOUND = 999999.999;

    /** Length of confirmedPlantCd in characters; one position per process. */
    public static final int CONFIRMED_PLANT_CD_LENGTH = 8;

    /** Inactive process marker in confirmedPlantCd. */
    public static final char INACTIVE_PROCESS = ' ';

    /** SLAB_RESULT.SLAB_NO is a 12-digit zero-padded string. */
    public static final int SLAB_NO_DIGITS = 12;

    /** 8 production processes in confirmedPlantCd position order. */
    public static final String[] PROC_CODES = {
        "SM", "HR", "HRF", "CR", "ANL1", "ANL2", "GAL", "CRF"
    };

    private SdConstants() {}
}
```

- [ ] **Step 2: Replace magic numbers in copied wrapper files (if any)**

Search for occurrences and replace with `SdConstants.X` references where appropriate. Do not change semantics.

- [ ] **Step 3: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/common/
git commit -m "feat(slab-v2/feature): SdConstants extraction (DEFAULT_PRODUCTIVITY, NO_UPPER_BOUND, ...)"
```

---

## Phase 4 — Std Lookup Services

### Task 4.1: Copy std/wrapper + std/service (9 files)

Source (v1):
```
slab-design-feature/.../sd/process/std/
├── action/SdStdAction.java
├── service/CastSpecService.java, CustomerStdService.java, EdgingService.java,
│           HrMaxWgtService.java, HrMinWgtService.java, HrSpecService.java,
│           PlantMappingService.java, ProductivityService.java,
│           SdStdService.java, SpecificGravityProvider.java
└── wrapper/SdStdDto.java
```

- [ ] **Step 1: Copy std subtree**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/. \
      $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/
```

- [ ] **Step 2: Update imports for moved store packages**

Replace in each std/service file:
- `import com.example.slabdesign.store.sd.std.oracle.jpo.` → `import com.example.slabdesign.store.sd.std.jpo.`
- `import com.example.slabdesign.store.sd.std.oracle.repository.` → `import com.example.slabdesign.store.sd.std.repository.`

Use grep to locate, then Edit each file.

- [ ] **Step 3: Apply drama-DNA cleanup**

- Replace `0.95` → `SdConstants.DEFAULT_PRODUCTIVITY` in `ProductivityService` (verify identical numeric).
- Replace `7.82` → `SdConstants.DEFAULT_SPECIFIC_GRAVITY` in `SpecificGravityProvider`.
- Replace `999999.999` → `SdConstants.NO_UPPER_BOUND` wherever appears.
- Add `import com.example.slabdesign.feature.sd.common.SdConstants;`
- Apply productCd field renames if any service reads order.productTypeCd/etc.

- [ ] **Step 4: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/
git commit -m "feat(slab-v2/feature): copy std lookup services + SdConstants references"
```

---

## Phase 5 — Working Actions (21 algorithm steps + helpers)

This phase ports 23 action classes from v1 with the cleanup pass. Group by algorithm phase.

### Task 5.1: Copy + clean Phase 1 actions (validator, classifier, helpers)

**Files (v1 → v2):**
- `SdOrderValidator.java`, `SdProductClassifier.java`, `SdOrderExtractor.java`, `SelectedHrTgtWidthResolver.java`, `SdConstraintCheckAction.java`, `SdObjectiveAction.java`

- [ ] **Step 1: Copy entire working/action/ tree (will batch-clean across tasks)**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp -R $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/. \
      $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/
```

- [ ] **Step 2: Apply blanket renames across all 23 files**

Run a grep + Edit pass over `v2/.../working/action/*.java`:
- Imports `store.sd.std.oracle.{jpo,repository}` → `store.sd.std.{jpo,repository}`
- Imports `store.sd.working.oracle.{jpo,repository}` → `store.sd.working.{jpo,repository}`
- Imports `store.sd.history.oracle.{jpo,repository}` → `store.sd.history.{jpo,repository}`
- `productTypeCd|productNameCd|productKindCd` → `productCd` (field references)
- `0.95` → `SdConstants.DEFAULT_PRODUCTIVITY` (with import)
- `999999.999` → `SdConstants.NO_UPPER_BOUND`

Also remove `// @author 김... (YYYY-MM-DD)` lines.

- [ ] **Step 3: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```
Expected: BUILD SUCCESS.

- [ ] **Step 4: Write unit test for `SdOrderValidator`**

Read v1 `SdOrderValidator.java` to discover its dependencies (likely repository or service injections) and DG codes (DG001-005).

Write to `V2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/process/working/action/SdOrderValidatorTest.java`:
```java
package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SdOrderValidatorTest {

    private final SdOrderValidator validator = new SdOrderValidator();

    @Test
    void dg001_stockOrder_throws() {
        SDOrderEntity order = newOrder();
        order.setStockCode("1");
        assertThatThrownBy(() -> validator.validate(order))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.DG001);
    }

    @Test
    void dg002_zeroOrderWidth_throws() {
        SDOrderEntity order = newOrder();
        order.setOrderWidth(0.0);
        assertThatThrownBy(() -> validator.validate(order))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.DG002);
    }

    @Test
    void allValidationsPass_returnsNormally() {
        SDOrderEntity order = newOrder();
        validator.validate(order);  // no throw
    }

    private SDOrderEntity newOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD20260510001");
        o.setStockCode("0");
        o.setOrderWidth(1200.0);
        o.setOrderLength(8500.0);
        // ... fill required fields based on v1 validator's read pattern
        return o;
    }
}
```

Adjust the test based on actual `SdOrderValidator` constructor signature. If it requires repositories, use `@ExtendWith(MockitoExtension.class)` + `@Mock`.

- [ ] **Step 5: Run validator test, verify pass**

```bash
./mvnw -pl slab-design-feature test -Dtest=SdOrderValidatorTest
```

- [ ] **Step 6: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/
git commit -m "feat(slab-v2/feature): copy working/action/ all 23 files with cleanup + validator test"
```

---

### Task 5.2: Unit tests for one-shot steps 1-7

Each test stub follows this template per action; adapt fields based on each action's actual signature read from v1.

**Files:**
- Create: `V2/slab-design-feature/src/test/java/.../SdThicknessActionTest.java`
- Create: `SdWidthRangeActionTest.java`
- Create: `SdLengthRangeActionTest.java`
- Create: `SdFirstWeightActionTest.java`
- Create: `SdSecondWgtLowActionTest.java`
- Create: `SdSecondWgtHighActionTest.java`
- Create: `SdMaxSplitCountActionTest.java`

- [ ] **Step 1: Write SdThicknessActionTest skeleton**

Pattern (adapt for each):
```java
package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SdThicknessActionTest {

    @Mock CastSpecService castSpecService;

    @Test
    void normal_castSpecPresent_setsSlabThickness() {
        when(castSpecService.findThickness(any())).thenReturn(Optional.of(230.0));
        SdThicknessAction action = new SdThicknessAction(castSpecService);
        SDOrderEntity order = sampleOrder();
        SDSlabEntity slab = new SDSlabEntity();
        action.run(order, slab);
        assertThat(slab.getSlabThickness()).isEqualTo(230.0);
    }

    @Test
    void dg101_castSpecMissing_throws() {
        when(castSpecService.findThickness(any())).thenReturn(Optional.empty());
        SdThicknessAction action = new SdThicknessAction(castSpecService);
        assertThatThrownBy(() -> action.run(sampleOrder(), new SDSlabEntity()))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.DG101);
    }

    private SDOrderEntity sampleOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD20260510001");
        o.setProductCd("COIL");
        o.setOrderWidth(1200.0);
        return o;
    }
}
```

Adjust constructor signature, mock dependencies, and field/method names by reading the actual `SdThicknessAction.java` from v2 (which is the cleaned copy from v1).

- [ ] **Step 2: Replicate pattern for the other 6 step actions**

For each of `SdWidthRangeAction`, `SdLengthRangeAction`, `SdFirstWeightAction`, `SdSecondWgtLowAction`, `SdSecondWgtHighAction`, `SdMaxSplitCountAction`:
1. Read the v2 action file to identify constructor deps + run method signature + DG codes thrown.
2. Write 2-4 tests: normal case, each DG code path, boundary if applicable.

- [ ] **Step 3: Run tests**

```bash
./mvnw -pl slab-design-feature test
```
Expected: all 7 step-1-7 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/test/
git commit -m "test(slab-v2/feature): unit tests for steps 1-7 actions (one-shot)"
```

---

### Task 5.3: Unit tests for A-a loop steps 8-13

**Files:**
- Create: `SdSplitRangeActionTest.java` (step 8)
- Create: `SdSlabCountActionTest.java` (step 9)
- Create: `SdInitialSlabWgtActionTest.java` (step 10)
- Create: `SdSlabWgtRecalcActionTest.java` (step 12-13)
- Create: `SdSlabSizeCalcActionTest.java` (helper)

- [ ] **Step 1: Write tests following the same pattern as Task 5.2**

For each action: 1-2 normal cases + 1-2 fail/retry cases. The retry semantics (signal that A-a loop should decrement splitCount) is communicated via boolean return or exception type — read v1 carefully.

- [ ] **Step 2: Run**

```bash
./mvnw -pl slab-design-feature test
```

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/test/
git commit -m "test(slab-v2/feature): unit tests for A-a loop steps 8-13"
```

---

### Task 5.4: Unit tests for steps 16-21 + helpers

**Files:**
- Create: `SdFinalWidthRangeActionTest.java` (step 16)
- Create: `SdFinalLengthRangeActionTest.java` (step 17)
- Create: `SdTargetWidthActionTest.java` (step 18)
- Create: `SdTargetLengthActionTest.java` (step 19)
- Create: `SdSlabSaveActionTest.java` (step 20)
- Create: `SdProductClassifierTest.java`
- Create: `SdOrderExtractorTest.java`
- Create: `SelectedHrTgtWidthResolverTest.java`
- Create: `SdConstraintCheckActionTest.java`

- [ ] **Step 1: Write tests** (same pattern)

- [ ] **Step 2: Run**

```bash
./mvnw -pl slab-design-feature test
```

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/test/
git commit -m "test(slab-v2/feature): unit tests for steps 16-21 + helper actions"
```

---

## Phase 6 — Designer + Driver + Trace Infrastructure

### Task 6.1: `StepTrace` record + `TraceCollector`

**Files:**
- Create: `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/StepTrace.java`
- Create: `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/TraceCollector.java`
- Create: `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/TraceStatus.java`

- [ ] **Step 1: Write `TraceStatus` enum**

Write to `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/TraceStatus.java`:
```java
package com.example.slabdesign.feature.sd.trace;

public enum TraceStatus {
    OK,
    RETRY,
    FAIL,
    SKIP
}
```

- [ ] **Step 2: Write `StepTrace` record**

Write to `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/StepTrace.java`:
```java
package com.example.slabdesign.feature.sd.trace;

import java.util.Map;

public record StepTrace(
    int step,
    String stepName,
    String phase,
    int iteration,
    Map<String, Object> input,
    Map<String, Object> output,
    TraceStatus status,
    String errorCode,
    String errorMessage,
    double elapsedMs
) {}
```

- [ ] **Step 3: Write test for `TraceCollector`**

Write to `V2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/trace/TraceCollectorTest.java`:
```java
package com.example.slabdesign.feature.sd.trace;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TraceCollectorTest {

    @Test
    void wrap_okPath_recordsOkTrace() {
        TraceCollector collector = new TraceCollector();
        Object result = collector.wrap(1, "SdThicknessAction", "ONE_SHOT", 1,
            Map.of("orderWidth", 1200.0),
            () -> { return Map.of("slabThickness", 230.0); });
        assertThat(result).isEqualTo(Map.of("slabThickness", 230.0));
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.OK);
        assertThat(t.errorCode()).isNull();
        assertThat(t.elapsedMs()).isGreaterThanOrEqualTo(0);
    }

    @Test
    void wrap_algorithmException_recordsFailTraceAndRethrows() {
        TraceCollector collector = new TraceCollector();
        assertThatThrownBy(() -> collector.wrap(2, "SdWidthRangeAction", "ONE_SHOT", 1,
            Map.of(),
            () -> { throw new AlgorithmException(SdErrorCode.DG104, "invalid"); }))
            .isInstanceOf(AlgorithmException.class);
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.FAIL);
        assertThat(t.errorCode()).isEqualTo("DG104");
    }
}
```

- [ ] **Step 4: Run, see fail**

```bash
./mvnw -pl slab-design-feature test -Dtest=TraceCollectorTest
```
Expected: COMPILATION FAIL (TraceCollector not yet implemented).

- [ ] **Step 5: Implement `TraceCollector`**

Write to `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/TraceCollector.java`:
```java
package com.example.slabdesign.feature.sd.trace;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * Collects per-step input/output snapshots during slab design execution.
 * Inject as nullable into SdDesigner — null = trace disabled (zero overhead).
 */
public class TraceCollector {

    private final List<StepTrace> traces = new ArrayList<>();

    public List<StepTrace> traces() {
        return List.copyOf(traces);
    }

    /**
     * Wrap an action invocation with trace capture.
     * @param step      step number (1-21)
     * @param stepName  short class name of the action
     * @param phase     ONE_SHOT | AA_LOOP | FINAL | SAVE
     * @param iteration 1 for one-shot phases, increments inside A-a loop
     * @param input     snapshot of action input as map
     * @param body      the action invocation
     * @return the body's return value
     */
    @SuppressWarnings("unchecked")
    public <T> T wrap(int step, String stepName, String phase, int iteration,
                      Map<String, Object> input, Supplier<T> body) {
        long t0 = System.nanoTime();
        try {
            T result = body.get();
            double ms = (System.nanoTime() - t0) / 1_000_000.0;
            Map<String, Object> output = result instanceof Map<?, ?> m
                ? (Map<String, Object>) m
                : Map.of("result", result);
            traces.add(new StepTrace(step, stepName, phase, iteration, input, output,
                TraceStatus.OK, null, null, ms));
            return result;
        } catch (AlgorithmException e) {
            double ms = (System.nanoTime() - t0) / 1_000_000.0;
            traces.add(new StepTrace(step, stepName, phase, iteration, input, null,
                TraceStatus.FAIL, e.getErrorCode().name(), e.getMessage(), ms));
            throw e;
        }
    }

    public void recordRetry(int step, String stepName, String phase, int iteration,
                            Map<String, Object> input, String reason) {
        traces.add(new StepTrace(step, stepName, phase, iteration, input, null,
            TraceStatus.RETRY, null, reason, 0));
    }

    public void recordSkip(int step, String stepName, String phase, String reason) {
        traces.add(new StepTrace(step, stepName, phase, 1, Map.of(), null,
            TraceStatus.SKIP, null, reason, 0));
    }
}
```

- [ ] **Step 6: Run test, verify pass**

```bash
./mvnw -pl slab-design-feature test -Dtest=TraceCollectorTest
```

- [ ] **Step 7: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/trace/
git add sample-repos/slab-design-real_v2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/trace/
git commit -m "feat(slab-v2/feature): TraceCollector + StepTrace record"
```

---

### Task 6.2: Copy + adapt `SdDesigner` with optional trace

**Files:**
- Modify (copy from v1, then edit): `V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/designer/SdDesigner.java`
- Copy: history wrapper / service / action under `feature/sd/process/history/`
- Copy: working service `SdWorkingService.java`, `SlabNoSequence.java`

- [ ] **Step 1: Copy designer + history + working/service from v1**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/designer/SdDesigner.java \
   $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/designer/SdDesigner.java
cp -R $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/history/. \
      $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/history/
cp $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/service/SdWorkingService.java \
   $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/service/SdWorkingService.java
cp $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/service/SlabNoSequence.java \
   $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/service/SlabNoSequence.java
```

- [ ] **Step 2: Apply blanket renames**

Run grep across the copied files:
- `store.sd.*.oracle.{jpo,repository}` → `store.sd.*.{jpo,repository}` (3 subtree variants)
- magic numbers → SdConstants
- `productTypeCd|productNameCd|productKindCd` → `productCd`
- Remove `@author 김...` lines

- [ ] **Step 3: Add optional `TraceCollector` parameter to `SdDesigner.designOne(...)`**

Read v2 `SdDesigner.java`. The method that drives one order's design (likely `designOne(SDOrderEntity)` or similar) needs an overload:

```java
public SDSlabEntity designOne(SDOrderEntity order) {
    return designOne(order, null);
}

public SDSlabEntity designOne(SDOrderEntity order, TraceCollector trace) {
    // existing 21-step body, with each action call wrapped via trace if non-null
}
```

For each action call site, change from:
```java
thicknessAction.run(order, slab);
```
to:
```java
runStep(1, "SdThicknessAction", "ONE_SHOT", 1, order, slab, trace,
    () -> thicknessAction.run(order, slab));
```

Add a private helper `runStep(int, String, String, int, ..., TraceCollector, Runnable)` that:
- If trace == null → just runs the body
- Else → wraps via collector.wrap(...)

For the A-a loop: pass current iteration count to the wrapped step 8-13 calls.

For the validator phase 1.1: wrap with phase="VALIDATION".

- [ ] **Step 4: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```

- [ ] **Step 5: Write a designer integration test (no DB, all mocks)**

Write to `V2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/designer/SdDesignerTraceTest.java`:
```java
package com.example.slabdesign.feature.sd.designer;

import com.example.slabdesign.feature.sd.trace.TraceCollector;
import com.example.slabdesign.feature.sd.trace.TraceStatus;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SdDesignerTraceTest {

    @Test
    void designOne_withTraceCollector_capturesPerStepEntries() {
        // Build SdDesigner with mocked dependencies returning happy-path values.
        // (Setup omitted; mirror v1 test if any, or instantiate each Sd*Action with mocks.)
        SdDesigner designer = buildHappyPathDesigner();
        TraceCollector trace = new TraceCollector();
        SDOrderEntity order = sampleHappyOrder();
        designer.designOne(order, trace);
        assertThat(trace.traces()).isNotEmpty();
        assertThat(trace.traces()).extracting("status")
            .doesNotContain(TraceStatus.FAIL);
    }

    private SdDesigner buildHappyPathDesigner() { /* TODO inline mocks */ return null; }
    private SDOrderEntity sampleHappyOrder() { /* TODO build entity */ return null; }
}
```

This is a placeholder that will be filled in when actual designer wiring is verified. Mark as `@Disabled` if mocks are too complex; integration tests in Phase 9 cover end-to-end.

- [ ] **Step 6: Run tests**

```bash
./mvnw -pl slab-design-feature test
```

- [ ] **Step 7: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/
git add sample-repos/slab-design-real_v2/slab-design-feature/src/test/java/com/example/slabdesign/feature/sd/designer/
git commit -m "feat(slab-v2/feature): SdDesigner with optional TraceCollector + history/service copies"
```

---

### Task 6.3: Copy + simplify `SdDriver`

V1's `SdDriver.batchDesign(cmpCd, orgCd)` likely orchestrates: load all orders for company-org → loop → designer.designOne. Kafka publishing might appear; remove it.

- [ ] **Step 1: Copy SdDriver.java**

```bash
V1=sample-repos/slab-design-real
V2=sample-repos/slab-design-real_v2
cp $V1/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/driver/SdDriver.java \
   $V2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/driver/SdDriver.java
```

- [ ] **Step 2: Apply renames + remove Kafka**

Read v2 SdDriver.java. If it has:
- `import org.springframework.cloud.stream.*` or `import org.apache.kafka.*` — remove
- `@Output`, `@StreamListener`, `MessageChannel`, `KafkaTemplate` — remove
- Any "publish event" call — remove (v2 batchDesign returns BatchResult directly)

Apply blanket renames (oracle.{jpo,repository} → {jpo,repository}, productCd, magic numbers).

The result must expose:
```java
public BatchResult batchDesign(String cmpCd, String orgCd);
public SDSlabEntity singleDesign(String cmpCd, String orgCd, String orderNo);
public SDSlabEntity singleDesign(String cmpCd, String orgCd, String orderNo, TraceCollector trace);
```

Add `singleDesign(...)` if not present in v1 — straightforward: find one order via `SDOrderOsRepository.findById`, hydrate via SdMapper + extractor, call `designer.designOne(order, trace)`.

- [ ] **Step 3: Compile**

```bash
./mvnw -pl slab-design-feature compile -am
```

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/driver/
git commit -m "feat(slab-v2/feature): SdDriver simplified — kafka removed, singleDesign added"
```

---

## Phase 7 — REST Controllers + Swagger

### Task 7.1: `SdWorkingController` — batch + single + trace

**Files:**
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/working/SdWorkingController.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/working/dto/SingleDesignRequest.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/working/dto/SingleDesignResponse.java`

- [ ] **Step 1: Write request DTO**

Write to `dto/SingleDesignRequest.java`:
```java
package com.example.slabdesign.facade.sd.rest.working.dto;

public record SingleDesignRequest(
    String cmpCd,
    String orgCd,
    String orderNo
) {}
```

- [ ] **Step 2: Write response DTO**

Write to `dto/SingleDesignResponse.java`:
```java
package com.example.slabdesign.facade.sd.rest.working.dto;

import com.example.slabdesign.feature.sd.trace.StepTrace;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;

import java.util.List;

public record SingleDesignResponse(
    List<SDSlabEntity> slabResults,
    String errorCode,
    String errorMessage,
    List<StepTrace> trace
) {
    public static SingleDesignResponse ok(List<SDSlabEntity> slabs) {
        return new SingleDesignResponse(slabs, null, null, null);
    }
    public static SingleDesignResponse okWithTrace(List<SDSlabEntity> slabs, List<StepTrace> trace) {
        return new SingleDesignResponse(slabs, null, null, trace);
    }
    public static SingleDesignResponse fail(String code, String message, List<StepTrace> trace) {
        return new SingleDesignResponse(List.of(), code, message, trace);
    }
}
```

- [ ] **Step 3: Write controller**

Write to `SdWorkingController.java`:
```java
package com.example.slabdesign.facade.sd.rest.working;

import com.example.slabdesign.facade.sd.rest.working.dto.SingleDesignRequest;
import com.example.slabdesign.facade.sd.rest.working.dto.SingleDesignResponse;
import com.example.slabdesign.feature.sd.driver.SdDriver;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.trace.TraceCollector;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/sd/working")
@Tag(name = "Working", description = "21-step slab design execution")
public class SdWorkingController {

    private final SdDriver driver;

    public SdWorkingController(SdDriver driver) {
        this.driver = driver;
    }

    @Operation(summary = "회사·소 단위 배치 슬랩 설계 (v1 호환)")
    @PostMapping("/batch")
    public SdDriver.BatchResult batchDesign(
            @RequestParam String cmpCd,
            @RequestParam String orgCd) {
        return driver.batchDesign(cmpCd, orgCd);
    }

    @Operation(summary = "주문 1건 슬랩 설계 (옵션: trace=true 로 step-별 입출력 trace 반환)")
    @PostMapping("/single")
    public SingleDesignResponse singleDesign(
            @RequestBody SingleDesignRequest req,
            @RequestParam(defaultValue = "false") boolean trace) {
        TraceCollector collector = trace ? new TraceCollector() : null;
        try {
            SDSlabEntity slab = driver.singleDesign(req.cmpCd(), req.orgCd(), req.orderNo(), collector);
            List<SDSlabEntity> slabs = slab == null ? List.of() : List.of(slab);
            return collector == null
                ? SingleDesignResponse.ok(slabs)
                : SingleDesignResponse.okWithTrace(slabs, collector.traces());
        } catch (AlgorithmException e) {
            return SingleDesignResponse.fail(
                e.getErrorCode().name(),
                e.getMessage(),
                collector == null ? null : collector.traces());
        }
    }
}
```

Note: if `driver.singleDesign` returns `List<SDSlabEntity>` (multi-slab from one order), adjust to handle the list directly.

- [ ] **Step 4: Compile**

```bash
./mvnw -pl slab-design-facade compile -am
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/working/
git commit -m "feat(slab-v2/facade): SdWorkingController batch + single (trace optional)"
```

---

### Task 7.2: `SdOrderController` — order list / detail

**Files:**
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/orders/SdOrderController.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/orders/dto/OrderSummary.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/orders/dto/OrderDetail.java`

- [ ] **Step 1: DTOs**

Write `OrderSummary.java`:
```java
package com.example.slabdesign.facade.sd.rest.orders.dto;

public record OrderSummary(
    String cmpCd,
    String orgCd,
    String orderNo,
    String productCd,
    String confirmedPlantCd,
    Double orderWidth,
    Double orderLength
) {}
```

Write `OrderDetail.java`:
```java
package com.example.slabdesign.facade.sd.rest.orders.dto;

import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderQdJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderChemicalJpo;

public record OrderDetail(
    SDOrderOsJpo os,
    SDOrderOmJpo om,
    SDOrderQdJpo qd,
    SDOrderChemicalJpo chemical
) {}
```

- [ ] **Step 2: Controller**

Write `SdOrderController.java`:
```java
package com.example.slabdesign.facade.sd.rest.orders;

import com.example.slabdesign.facade.sd.rest.orders.dto.OrderDetail;
import com.example.slabdesign.facade.sd.rest.orders.dto.OrderSummary;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.working.repository.SDOrderChemicalRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOmRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOsRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderQdRepository;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sd/orders")
@Tag(name = "Orders", description = "Seeded order browsing")
public class SdOrderController {

    private final SDOrderOsRepository osRepo;
    private final SDOrderOmRepository omRepo;
    private final SDOrderQdRepository qdRepo;
    private final SDOrderChemicalRepository chemRepo;

    public SdOrderController(SDOrderOsRepository osRepo,
                             SDOrderOmRepository omRepo,
                             SDOrderQdRepository qdRepo,
                             SDOrderChemicalRepository chemRepo) {
        this.osRepo = osRepo;
        this.omRepo = omRepo;
        this.qdRepo = qdRepo;
        this.chemRepo = chemRepo;
    }

    @GetMapping
    public List<OrderSummary> list(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return osRepo.findByCmpCdAndOrgCd(cmpCd, orgCd, PageRequest.of(page, size))
            .stream().map(this::toSummary).toList();
    }

    @GetMapping("/{cmpCd}/{orgCd}/{orderNo}")
    public OrderDetail detail(@PathVariable String cmpCd,
                              @PathVariable String orgCd,
                              @PathVariable String orderNo) {
        SDOrderPK pk = new SDOrderPK(cmpCd, orgCd, orderNo);
        return new OrderDetail(
            osRepo.findById(pk).orElseThrow(),
            omRepo.findById(pk).orElseThrow(),
            qdRepo.findById(pk).orElseThrow(),
            chemRepo.findById(pk).orElseThrow()
        );
    }

    private OrderSummary toSummary(SDOrderOsJpo os) {
        return new OrderSummary(os.getCmpCd(), os.getOrgCd(), os.getOrderNo(),
            os.getProductCd(), os.getConfirmedPlantCd(),
            os.getOrderWidth(), os.getOrderLength());
    }
}
```

- [ ] **Step 3: Add `findByCmpCdAndOrgCd` method to `SDOrderOsRepository`**

Edit `V2/slab-design-store/.../working/repository/SDOrderOsRepository.java` to add:
```java
java.util.List<com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo>
    findByCmpCdAndOrgCd(String cmpCd, String orgCd, org.springframework.data.domain.Pageable pageable);
```

(Spring Data JPA will derive the query from the method name.)

- [ ] **Step 4: Compile**

```bash
./mvnw compile -am -pl slab-design-facade
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "feat(slab-v2/facade): SdOrderController list + detail"
```

---

### Task 7.3: `SdResultController` — slab result query

**Files:**
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/results/SdResultController.java`

- [ ] **Step 1: Write controller**

```java
package com.example.slabdesign.facade.sd.rest.results;

import com.example.slabdesign.store.sd.working.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.repository.SlabResultRepository;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sd/results")
@Tag(name = "Results", description = "Slab result query")
public class SdResultController {

    private final SlabResultRepository repo;

    public SdResultController(SlabResultRepository repo) {
        this.repo = repo;
    }

    @GetMapping
    public List<SlabResultJpo> byOrder(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam String orderNo) {
        return repo.findByCmpCdAndOrgCdAndOrderNo(cmpCd, orgCd, orderNo);
    }

    @GetMapping("/{slabNo}")
    public SlabResultJpo bySlabNo(@PathVariable String slabNo) {
        return repo.findFirstBySlabNo(slabNo).orElseThrow();
    }
}
```

- [ ] **Step 2: Add derived methods to `SlabResultRepository`**

Edit to add:
```java
java.util.List<com.example.slabdesign.store.sd.working.jpo.SlabResultJpo>
    findByCmpCdAndOrgCdAndOrderNo(String cmpCd, String orgCd, String orderNo);
java.util.Optional<com.example.slabdesign.store.sd.working.jpo.SlabResultJpo>
    findFirstBySlabNo(String slabNo);
```

- [ ] **Step 3: Compile**

```bash
./mvnw compile -am -pl slab-design-facade
```

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "feat(slab-v2/facade): SdResultController slab query endpoints"
```

---

### Task 7.4: `SdHistoryController` — 21-step history query

**Files:**
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/history/SdHistoryController.java`

- [ ] **Step 1: Write controller**

```java
package com.example.slabdesign.facade.sd.rest.history;

import com.example.slabdesign.store.sd.history.jpo.SlabDesignHistJpo;
import com.example.slabdesign.store.sd.history.repository.SlabDesignHistRepository;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sd/history")
@Tag(name = "History", description = "21-step design history (post-execution)")
public class SdHistoryController {

    private final SlabDesignHistRepository repo;

    public SdHistoryController(SlabDesignHistRepository repo) {
        this.repo = repo;
    }

    @GetMapping
    public List<SlabDesignHistJpo> byOrder(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam String orderNo) {
        return repo.findByCmpCdAndOrgCdAndOrderNoOrderByStepNoAsc(cmpCd, orgCd, orderNo);
    }
}
```

- [ ] **Step 2: Add derived method to `SlabDesignHistRepository`**

Add:
```java
java.util.List<com.example.slabdesign.store.sd.history.jpo.SlabDesignHistJpo>
    findByCmpCdAndOrgCdAndOrderNoOrderByStepNoAsc(String cmpCd, String orgCd, String orderNo);
```

If v1's history table column for step is named differently (e.g., `seqNo`), use that name.

- [ ] **Step 3: Compile**

```bash
./mvnw compile -am -pl slab-design-facade
```

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "feat(slab-v2/facade): SdHistoryController per-order step history"
```

---

### Task 7.5: `SdSeedController` — reset + scenarios meta

**Files:**
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/seed/SdSeedController.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/seed/SeedService.java`
- Create: `V2/slab-design-facade/src/main/java/com/example/slabdesign/facade/sd/rest/seed/dto/ScenarioMeta.java`

- [ ] **Step 1: Scenario meta DTO**

Write `dto/ScenarioMeta.java`:
```java
package com.example.slabdesign.facade.sd.rest.seed.dto;

public record ScenarioMeta(
    String id,            // S1..S5
    String orderNo,
    String description,
    String confirmedPlantCd,
    String expectedOutcome // "1 slab", "4 slabs", "DG004 fail", ...
) {}
```

- [ ] **Step 2: SeedService**

Write `SeedService.java`:
```java
package com.example.slabdesign.facade.sd.rest.seed;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.Statement;

@Service
public class SeedService {

    @PersistenceContext private EntityManager em;
    private final DataSource dataSource;
    private final ResourceLoader resourceLoader;

    private static final String[] TABLES = {
        "SLAB_DESIGN_HIST", "SLAB_RESULT",
        "ORDER_CHEMICAL", "ORDER_QD", "ORDER_OM", "ORDER_OS",
        "EDGING_SPEC", "EDGING_GROUP", "HR_SPEC", "CAST_SPEC",
        "SD_PRODUCTIVITY_STD", "HR_MAX_WGT", "HR_MIN_WGT", "CUSTOMER_STD"
    };

    public SeedService(DataSource dataSource, ResourceLoader resourceLoader) {
        this.dataSource = dataSource;
        this.resourceLoader = resourceLoader;
    }

    @Transactional
    public void reset() throws Exception {
        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement()) {
            st.execute("SET REFERENTIAL_INTEGRITY FALSE");
            for (String table : TABLES) {
                try {
                    st.execute("TRUNCATE TABLE " + table);
                } catch (Exception ignored) {
                    // table absent (e.g., result/hist on first run) — skip
                }
            }
            st.execute("SET REFERENTIAL_INTEGRITY TRUE");

            Resource master = resourceLoader.getResource("classpath:db/seed/01_master.sql");
            Resource orders = resourceLoader.getResource("classpath:db/seed/02_orders.sql");
            ScriptUtils.executeSqlScript(conn, master);
            ScriptUtils.executeSqlScript(conn, orders);
        }
    }
}
```

(Adapt table names to actual schema — use the entity `@Table(name = ...)` values from v2 store entities. If a name looks wrong, search for `@Table` in `slab-design-real_v2/slab-design-store/` and fix.)

- [ ] **Step 3: Controller**

Write `SdSeedController.java`:
```java
package com.example.slabdesign.facade.sd.rest.seed;

import com.example.slabdesign.facade.sd.rest.seed.dto.ScenarioMeta;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sd/seed")
@Tag(name = "Seed", description = "Reset DB and inspect golden scenario metadata")
public class SdSeedController {

    private final SeedService seed;

    private static final List<ScenarioMeta> SCENARIOS = List.of(
        new ScenarioMeta("S1", "ORD20260510001", "일반 COIL 주문 (golden path)", "K   K   ", "1 slab"),
        new ScenarioMeta("S2", "ORD20260510002", "다중 분할 (maxSplitCount=4)", "KK      ", "4 slabs"),
        new ScenarioMeta("S3", "ORD20260510003", "A-a loop fallback", "KKKK    ", "splitCount-1 후 성공"),
        new ScenarioMeta("S4", "ORD20260510004", "DG004 포장단중 cross-check fail", "KK      ", "design fail + hist row"),
        new ScenarioMeta("S5", "ORD20260510005", "최소 활성 공정 (SM, CRF)", "K      K", "1 slab, 누적실수율 = SM*CRF")
    );

    public SdSeedController(SeedService seed) {
        this.seed = seed;
    }

    @PostMapping("/reset")
    public Map<String, Object> reset() throws Exception {
        seed.reset();
        return Map.of("ok", true, "scenarios", SCENARIOS.stream().map(ScenarioMeta::id).toList());
    }

    @GetMapping("/scenarios")
    public List<ScenarioMeta> scenarios() {
        return SCENARIOS;
    }
}
```

- [ ] **Step 4: Compile**

```bash
./mvnw -pl slab-design-facade compile -am
```

- [ ] **Step 5: Commit**

```bash
git add sample-repos/slab-design-real_v2/
git commit -m "feat(slab-v2/facade): SdSeedController reset + scenarios meta"
```

---

### Task 7.6: `SwaggerConfig` + verify `/swagger-ui.html`

**Files:**
- Create: `V2/slab-design-boot/src/main/java/com/example/slabdesign/boot/config/SwaggerConfig.java`

- [ ] **Step 1: Write SwaggerConfig**

```java
package com.example.slabdesign.boot.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI slabDesignOpenApi() {
        return new OpenAPI().info(new Info()
            .title("slab-design-real_v2 API")
            .version("1.0.0")
            .description("21-step slab design with H2 in-memory DB and step-trace responses for simulation verification."));
    }
}
```

- [ ] **Step 2: Run server briefly + curl swagger-ui**

In one shell, start:
```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw spring-boot:run -pl slab-design-boot &
SERVER_PID=$!
sleep 30
curl -sf http://localhost:8080/swagger-ui.html > /dev/null && echo "swagger-ui OK" || echo "swagger-ui FAIL"
curl -sf http://localhost:8080/v3/api-docs > /tmp/api-docs.json && wc -l /tmp/api-docs.json
kill $SERVER_PID
```

Expected: "swagger-ui OK" and api-docs.json non-empty.

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-boot/src/main/java/com/example/slabdesign/boot/config/SwaggerConfig.java
git commit -m "feat(slab-v2/boot): SwaggerConfig + verified /swagger-ui.html"
```

---

## Phase 8 — Seed Data (5 Scenarios)

### Task 8.1: `01_master.sql` (master tables)

**Files:**
- Modify: `V2/slab-design-boot/src/main/resources/db/seed/01_master.sql`

Reading required: actual `@Table(name=...)` and `@Column(name=...)` for each of the 8 master entities. Use grep:
```bash
grep -rn "@Table\|@Column" sample-repos/slab-design-real_v2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/
```

The seed must populate enough rows for all 5 scenarios to find their lookups. Minimum coverage:

- `CAST_SPEC`: rows for `K K01 SS400` (covers S1, S2, S3, S5) + `K K01 SS41` (covers S4)
- `HR_SPEC`: matching rows
- `EDGING_GROUP`, `EDGING_SPEC`: width-mapping rules with `*` wildcard fallback
- `CUSTOMER_STD`, `HR_MIN_WGT`, `HR_MAX_WGT`: customer specs
- `SD_PRODUCTIVITY_STD`: rows for each (cmpCd, orgCd, procCode, grade, prodKind, customer) used

- [ ] **Step 1: Write 01_master.sql**

Replace contents of `V2/slab-design-boot/src/main/resources/db/seed/01_master.sql`:
```sql
-- ============================================================
-- 01_master.sql — spec & rule master row seeds
-- Loaded by spring.sql.init after JPA ddl-auto creates schema.
-- Column / table names mirror @Entity definitions. If a column
-- name surprises you, grep @Column in v2 store entities.
-- ============================================================

-- CAST_SPEC : 강종 → 슬랩 두께
INSERT INTO CAST_SPEC (CMP_CD, ORG_CD, GRADE, PRODUCT_CD, SLAB_THICKNESS)
VALUES
  ('K', 'K01', 'SS400', 'COIL', 230),
  ('K', 'K01', 'SS41',  'COIL', 250);

-- HR_SPEC : 강종+폭 → HR 입력 규격
INSERT INTO HR_SPEC (CMP_CD, ORG_CD, GRADE, PRODUCT_CD, MIN_WIDTH, MAX_WIDTH, MIN_THICKNESS, MAX_THICKNESS)
VALUES
  ('K', 'K01', 'SS400', 'COIL',  800, 1500, 200, 280),
  ('K', 'K01', 'SS41',  'COIL',  800, 1500, 220, 300);

-- EDGING_GROUP : 슬랩→스트립 폭 변환 그룹
INSERT INTO EDGING_GROUP (CMP_CD, ORG_CD, GRADE, GROUP_CODE)
VALUES
  ('K', 'K01', 'SS400', 'EG-A'),
  ('K', 'K01', 'SS41',  'EG-B'),
  ('K', 'K01', '*',     'EG-DEFAULT');

-- EDGING_SPEC : 그룹+폭 → 스트립 폭 (wildcard '*' fallback)
INSERT INTO EDGING_SPEC (CMP_CD, ORG_CD, GROUP_CODE, ORDER_WIDTH, SLAB_WIDTH_LOW, SLAB_WIDTH_HIGH)
VALUES
  ('K', 'K01', 'EG-A',       1200,  900, 1100),
  ('K', 'K01', 'EG-A',       '*',  1000, 1300),
  ('K', 'K01', 'EG-B',       '*',   850, 1050),
  ('K', 'K01', 'EG-DEFAULT', '*',   800, 1500);

-- CUSTOMER_STD : 고객별 표준 (포장단중 등)
INSERT INTO CUSTOMER_STD (CMP_CD, ORG_CD, CUSTOMER_CD, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH)
VALUES
  ('K', 'K01', 'CUST-001',  3000, 12000),
  ('K', 'K01', 'CUST-FAIL',   100,   200);  -- S4 트리거용 (cross-check fail)

-- HR_MIN_WGT / HR_MAX_WGT : 2D sheet (강종, 폭) → 단중 한계
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, GRADE, PRODUCT_CD, MIN_WIDTH, MIN_WGT)
VALUES
  ('K', 'K01', 'SS400', 'COIL',  800, 4000),
  ('K', 'K01', 'SS400', 'COIL', 1100, 5000),
  ('K', 'K01', 'SS41',  'COIL',  800, 4500);

INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, GRADE, PRODUCT_CD, MAX_WIDTH, MAX_WGT)
VALUES
  ('K', 'K01', 'SS400', 'COIL',  800, 14000),
  ('K', 'K01', 'SS400', 'COIL', 1100, 15000),
  ('K', 'K01', 'SS41',  'COIL',  800, 13000);

-- SD_PRODUCTIVITY_STD : 8공정 누적실수율 lookup
-- procCode ∈ {SM, HR, HRF, CR, ANL1, ANL2, GAL, CRF}
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CODE, GRADE, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES
  ('K', 'K01', 'SM',  'SS400', 'COIL', 'CUST-001', 0.86),
  ('K', 'K01', 'HR',  'SS400', 'COIL', 'CUST-001', 0.92),
  ('K', 'K01', 'HRF', 'SS400', 'COIL', 'CUST-001', 0.95),
  ('K', 'K01', 'CR',  'SS400', 'COIL', 'CUST-001', 0.94),
  ('K', 'K01', 'ANL1','SS400', 'COIL', 'CUST-001', 0.97),
  ('K', 'K01', 'ANL2','SS400', 'COIL', 'CUST-001', 0.97),
  ('K', 'K01', 'GAL', 'SS400', 'COIL', 'CUST-001', 0.96),
  ('K', 'K01', 'CRF', 'SS400', 'COIL', 'CUST-001', 0.93),
  ('K', 'K01', 'SM',  'SS41',  'COIL', 'CUST-FAIL', 0.85),
  ('K', 'K01', 'HR',  'SS41',  'COIL', 'CUST-FAIL', 0.90);
```

NOTE: The above column names are best-guess. After writing, if Hibernate fails to match on app startup, grep `@Table` and `@Column` in entities and fix the SQL.

- [ ] **Step 2: Run integration smoke (no entities used yet, just SQL load)**

```bash
./mvnw -pl slab-design-boot test -Dtest=SmokeTest
```
Expected: PASS (Spring context starts, schema generates, master SQL loads).

If FAIL on missing column, grep entity, fix SQL, retry.

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-boot/src/main/resources/db/seed/01_master.sql
git commit -m "feat(slab-v2/seed): 01_master.sql for 5 scenarios"
```

---

### Task 8.2: `02_orders.sql` (5 scenario orders)

**Files:**
- Modify: `V2/slab-design-boot/src/main/resources/db/seed/02_orders.sql`

- [ ] **Step 1: Write 02_orders.sql**

Replace contents:
```sql
-- ============================================================
-- 02_orders.sql — 5 golden scenario orders
-- ============================================================

-- S1: normal COIL order (cmpCd=K, orgCd=K01, orderNo=ORD20260510001)
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO, STOCK_CODE, PRODUCT_CD, GRADE, CUSTOMER_CD,
                      ORDER_WIDTH, ORDER_LENGTH, CONFIRMED_PLANT_CD, WORK_DUE,
                      ORDER_QTY)
VALUES ('K', 'K01', 'ORD20260510001', '0', 'COIL', 'SS400', 'CUST-001',
        1200, 8500, 'K   K   ', '2026-12-31',
        12000);

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH, WORK_DUE)
VALUES ('K', 'K01', 'ORD20260510001', 5000, 12000, '2026-12-31');

INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, REMAINING_DESIGN_QTY)
VALUES ('K', 'K01', 'ORD20260510001', 12000);

INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO, CHEM_C, CHEM_SI, CHEM_MN)
VALUES ('K', 'K01', 'ORD20260510001', 0.18, 0.20, 0.50);

-- S2: large multi-split order (maxSplitCount=4 expected)
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO, STOCK_CODE, PRODUCT_CD, GRADE, CUSTOMER_CD,
                      ORDER_WIDTH, ORDER_LENGTH, CONFIRMED_PLANT_CD, WORK_DUE, ORDER_QTY)
VALUES ('K', 'K01', 'ORD20260510002', '0', 'COIL', 'SS400', 'CUST-001',
        1100, 32000, 'KK      ', '2026-12-31', 50000);
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH, WORK_DUE)
VALUES ('K', 'K01', 'ORD20260510002', 6000, 14000, '2026-12-31');
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, REMAINING_DESIGN_QTY)
VALUES ('K', 'K01', 'ORD20260510002', 50000);
INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO, CHEM_C, CHEM_SI, CHEM_MN)
VALUES ('K', 'K01', 'ORD20260510002', 0.18, 0.20, 0.50);

-- S3: A-a loop fallback order (initial splitCount must fail step 12-13, drop-1 succeeds)
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO, STOCK_CODE, PRODUCT_CD, GRADE, CUSTOMER_CD,
                      ORDER_WIDTH, ORDER_LENGTH, CONFIRMED_PLANT_CD, WORK_DUE, ORDER_QTY)
VALUES ('K', 'K01', 'ORD20260510003', '0', 'COIL', 'SS400', 'CUST-001',
        1300, 16000, 'KKKK    ', '2026-12-31', 22000);
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH, WORK_DUE)
VALUES ('K', 'K01', 'ORD20260510003', 5500, 11500, '2026-12-31');
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, REMAINING_DESIGN_QTY)
VALUES ('K', 'K01', 'ORD20260510003', 22000);
INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO, CHEM_C, CHEM_SI, CHEM_MN)
VALUES ('K', 'K01', 'ORD20260510003', 0.18, 0.20, 0.50);

-- S4: DG004 fail (포장단중 cross-check). CUSTOMER_CD=CUST-FAIL with low packaging window (100..200)
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO, STOCK_CODE, PRODUCT_CD, GRADE, CUSTOMER_CD,
                      ORDER_WIDTH, ORDER_LENGTH, CONFIRMED_PLANT_CD, WORK_DUE, ORDER_QTY)
VALUES ('K', 'K01', 'ORD20260510004', '0', 'COIL', 'SS41', 'CUST-FAIL',
        900, 5000, 'KK      ', '2026-12-31', 8000);
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH, WORK_DUE)
VALUES ('K', 'K01', 'ORD20260510004', 100, 200, '2026-12-31');
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, REMAINING_DESIGN_QTY)
VALUES ('K', 'K01', 'ORD20260510004', 8000);
INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO, CHEM_C, CHEM_SI, CHEM_MN)
VALUES ('K', 'K01', 'ORD20260510004', 0.20, 0.25, 0.55);

-- S5: minimal active processes (SM + CRF only)
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO, STOCK_CODE, PRODUCT_CD, GRADE, CUSTOMER_CD,
                      ORDER_WIDTH, ORDER_LENGTH, CONFIRMED_PLANT_CD, WORK_DUE, ORDER_QTY)
VALUES ('K', 'K01', 'ORD20260510005', '0', 'COIL', 'SS400', 'CUST-001',
        1100, 7000, 'K      K', '2026-12-31', 9000);
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO, PACKAGING_WGT_LOW, PACKAGING_WGT_HIGH, WORK_DUE)
VALUES ('K', 'K01', 'ORD20260510005', 4000, 11000, '2026-12-31');
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, REMAINING_DESIGN_QTY)
VALUES ('K', 'K01', 'ORD20260510005', 9000);
INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO, CHEM_C, CHEM_SI, CHEM_MN)
VALUES ('K', 'K01', 'ORD20260510005', 0.18, 0.20, 0.50);
```

NOTE: Adjust column names to match v2 entities. Specifically, columns like `STOCK_CODE`, `WORK_DUE`, `ORDER_QTY`, `REMAINING_DESIGN_QTY`, `CHEM_C` may differ — grep entities to verify. If a column doesn't exist in entity, drop it from INSERT.

- [ ] **Step 2: Verify integration smoke**

```bash
./mvnw -pl slab-design-boot test -Dtest=SmokeTest
```
Expected: PASS — Spring boots, schema + seed loads, no NullPointerException.

- [ ] **Step 3: Run server and curl orders endpoint**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw spring-boot:run -pl slab-design-boot &
SERVER_PID=$!
sleep 30
curl -sf 'http://localhost:8080/api/sd/orders?cmpCd=K&orgCd=K01' | head -c 500
echo
curl -sf 'http://localhost:8080/api/sd/seed/scenarios' | head -c 500
kill $SERVER_PID
```
Expected: 5 OrderSummary entries returned, 5 ScenarioMeta entries.

- [ ] **Step 4: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-boot/src/main/resources/db/seed/02_orders.sql
git commit -m "feat(slab-v2/seed): 02_orders.sql with 5 golden scenarios"
```

---

## Phase 9 — Tier 3 Golden Integration Tests

### Task 9.1: Test framework + S1 capture

**Files:**
- Create: `V2/slab-design-boot/src/test/java/com/example/slabdesign/boot/integration/ScenarioGoldenTest.java`
- Create: `V2/slab-design-boot/src/test/resources/golden/S1.json` (initially empty placeholder)

- [ ] **Step 1: Test class skeleton**

Write to `ScenarioGoldenTest.java`:
```java
package com.example.slabdesign.boot.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.restassured.RestAssured;
import io.restassured.http.ContentType;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.stream.Stream;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ScenarioGoldenTest {

    private static final ObjectMapper MAPPER = new ObjectMapper()
        .enable(SerializationFeature.INDENT_OUTPUT);
    private static final boolean REGEN = "true".equalsIgnoreCase(System.getenv("GOLDEN_REGEN"));

    @LocalServerPort int port;

    @BeforeEach
    void setup() {
        RestAssured.port = port;
        given().post("/api/sd/seed/reset").then().statusCode(200);
    }

    @TestFactory
    Stream<DynamicTest> scenarios() {
        return Stream.of(
            scenario("S1", "ORD20260510001"),
            scenario("S2", "ORD20260510002"),
            scenario("S3", "ORD20260510003"),
            scenario("S4", "ORD20260510004"),
            scenario("S5", "ORD20260510005")
        );
    }

    private DynamicTest scenario(String id, String orderNo) {
        return DynamicTest.dynamicTest(id, () -> {
            String body = """
                { "cmpCd": "K", "orgCd": "K01", "orderNo": "%s" }
                """.formatted(orderNo);
            String response = given()
                .contentType(ContentType.JSON)
                .body(body)
                .when()
                .post("/api/sd/working/single?trace=true")
                .then()
                .statusCode(200)
                .extract().asString();

            Path goldenPath = Paths.get("src/test/resources/golden/" + id + ".json");
            JsonNode actual = MAPPER.readTree(normalizeVolatile(response));

            if (REGEN || !Files.exists(goldenPath) || Files.size(goldenPath) == 0) {
                Files.writeString(goldenPath, MAPPER.writeValueAsString(actual));
                System.out.println("[GOLDEN_REGEN] wrote " + goldenPath);
                return;
            }

            JsonNode expected = MAPPER.readTree(Files.readString(goldenPath));
            assertThat(actual).isEqualTo(expected);
        });
    }

    /**
     * Strip volatile fields (timestamps, nano-elapsed) before comparing.
     */
    private String normalizeVolatile(String json) throws IOException {
        JsonNode tree = MAPPER.readTree(json);
        // Remove elapsedMs from each trace entry (timing varies)
        if (tree.has("trace") && tree.get("trace").isArray()) {
            tree.get("trace").forEach(node -> {
                if (node.isObject()) ((com.fasterxml.jackson.databind.node.ObjectNode) node).remove("elapsedMs");
            });
        }
        // Replace slabNo (sequence-derived) with marker
        if (tree.has("slabResults") && tree.get("slabResults").isArray()) {
            tree.get("slabResults").forEach(node -> {
                if (node.isObject() && node.has("slabNo")) {
                    ((com.fasterxml.jackson.databind.node.ObjectNode) node).put("slabNo", "__SEQ__");
                }
                if (node.isObject() && node.has("createdAt")) {
                    ((com.fasterxml.jackson.databind.node.ObjectNode) node).put("createdAt", "__TS__");
                }
            });
        }
        return MAPPER.writeValueAsString(tree);
    }
}
```

- [ ] **Step 2: Create empty golden files**

```bash
V2=sample-repos/slab-design-real_v2
for s in S1 S2 S3 S4 S5; do : > $V2/slab-design-boot/src/test/resources/golden/$s.json; done
```

- [ ] **Step 3: First run with `GOLDEN_REGEN=true` to capture goldens**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
GOLDEN_REGEN=true ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest
```
Expected: 5 dynamic tests. Each test prints `[GOLDEN_REGEN] wrote ...`. All pass (regen mode skips assertion).

If a scenario throws AlgorithmException unexpectedly, inspect:
```bash
curl -sf -H 'Content-Type: application/json' -d '{"cmpCd":"K","orgCd":"K01","orderNo":"ORD20260510001"}' \
  'http://localhost:8080/api/sd/working/single?trace=true' | python3 -m json.tool
```
Adjust seed data values until each scenario reaches its intended outcome (S1-S3, S5 produce slabs; S4 returns DG004 in errorCode).

- [ ] **Step 4: Manual review of golden files**

Open each `golden/S{1..5}.json` and verify:
- S1: 1 slab, trace has 21 OK steps, no FAIL
- S2: 4 slabs, trace shows maxSplitCount=4
- S3: trace contains RETRY status in A-a loop iteration 1, OK in iteration 2
- S4: errorCode = "DG004", slabResults empty
- S5: 1 slab, productivity uses only SM + CRF processes

If any value is unexpected, adjust seeds or algorithm understanding, regenerate.

- [ ] **Step 5: Re-run without REGEN to confirm goldens stable**

```bash
./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest
```
Expected: 5 scenarios PASS via assertion (not regen).

- [ ] **Step 6: Commit**

```bash
git add sample-repos/slab-design-real_v2/slab-design-boot/src/test/
git commit -m "test(slab-v2/integration): scenario golden test (5 scenarios) with GOLDEN_REGEN env"
```

---

### Task 9.2: Run full `mvnw verify` end-to-end

- [ ] **Step 1: Run full build + test suite**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw clean verify
```
Expected: BUILD SUCCESS. All Tier 1 (unit) + Tier 2 (repository) + Tier 3 (scenario golden) tests pass.

- [ ] **Step 2: Manual API curl exercise**

In one shell:
```bash
./mvnw spring-boot:run -pl slab-design-boot &
SERVER_PID=$!
sleep 30
```

In another shell, exercise each endpoint:
```bash
# 1. seed/scenarios
curl -sf http://localhost:8080/api/sd/seed/scenarios | python3 -m json.tool

# 2. orders list
curl -sf 'http://localhost:8080/api/sd/orders?cmpCd=K&orgCd=K01' | python3 -m json.tool

# 3. order detail
curl -sf http://localhost:8080/api/sd/orders/K/K01/ORD20260510001 | python3 -m json.tool

# 4. single design (trace)
curl -sf -X POST -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"K01","orderNo":"ORD20260510001"}' \
  'http://localhost:8080/api/sd/working/single?trace=true' | python3 -m json.tool

# 5. results
curl -sf 'http://localhost:8080/api/sd/results?cmpCd=K&orgCd=K01&orderNo=ORD20260510001' | python3 -m json.tool

# 6. history
curl -sf 'http://localhost:8080/api/sd/history?cmpCd=K&orgCd=K01&orderNo=ORD20260510001' | python3 -m json.tool

# 7. batch
curl -sf -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=K01' | python3 -m json.tool

# 8. seed reset
curl -sf -X POST http://localhost:8080/api/sd/seed/reset | python3 -m json.tool
```

All should return valid JSON. Document any unexpected responses for fix.

```bash
kill $SERVER_PID
```

- [ ] **Step 3: Commit nothing if all green; otherwise fix issues found and commit**

If issues found, fix in dedicated commits with `fix(slab-v2/...):` prefix.

---

## Phase 10 — Documentation

### Task 10.1: README.md

**Files:**
- Create: `V2/README.md`

- [ ] **Step 1: Write README**

```markdown
# slab-design-real_v2

자체 완결 실행 가능한 21-step 슬랩 설계 데모 + 시뮬레이션 검증 baseline.

## 빌드 / 실행

요구사항: JDK 21 (Maven Wrapper 동봉, Maven 별도 설치 불필요).

\```bash
./mvnw clean verify                 # 빌드 + 모든 테스트
./mvnw spring-boot:run -pl slab-design-boot   # 서버 기동 (port 8080)
\```

## API 탐색

- Swagger UI : http://localhost:8080/swagger-ui.html
- H2 Console : http://localhost:8080/h2-console (JDBC URL: `jdbc:h2:mem:slabdesign`, user: `sa`, pwd: 비움)

## 5개 골든 시나리오

상세는 `docs/SCENARIOS.md`. 요약:

| ID | 주문번호 | 의도 |
|----|---------|------|
| S1 | ORD20260510001 | 일반 COIL 골든 패스 |
| S2 | ORD20260510002 | 다중 분할 (maxSplitCount=4) |
| S3 | ORD20260510003 | A-a loop fallback |
| S4 | ORD20260510004 | DG004 포장단중 cross-check fail |
| S5 | ORD20260510005 | 최소 활성 공정 (SM, CRF) |

## 시뮬레이션 검증 인터페이스

`POST /api/sd/working/single?trace=true` 응답의 `trace[]`가 정답 인터페이스.
onTong이 ontology 기반으로 생성한 Python 코드를 동일 입력으로 실행해 step별 비교 가능.

## 골든 갱신

알고리즘 의도된 변경 시:
\```bash
GOLDEN_REGEN=true ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest
\```
재생성 후 `docs/SCENARIOS.md` 변경점 기록.

## v1과의 관계

`sample-repos/slab-design-real/` (read-only)을 베이스로 drama DNA를 정리하고 H2 + 시드를 추가한 깨끗한 baseline. 알고리즘 출력은 동일.

상세 차이는 `docs/V1_TO_V2_DIFF.md`.
```

- [ ] **Step 2: Commit**

```bash
git add sample-repos/slab-design-real_v2/README.md
git commit -m "docs(slab-v2): README with build / run / scenario quick-ref"
```

---

### Task 10.2: API.md (curl examples)

**Files:**
- Create: `V2/docs/API.md`

- [ ] **Step 1: Write API.md**

```markdown
# API Reference (slab-design-real_v2)

기본 호스트: `http://localhost:8080`
Swagger UI : `/swagger-ui.html`
OpenAPI JSON: `/v3/api-docs`

## 1. 슬랩 설계 실행 (Working)

### POST /api/sd/working/batch

회사·소 단위 배치 슬랩 설계 (v1 호환).

\```bash
curl -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=K01'
\```

응답: `BatchResult { total, processedCount, skippedCount, processedSlabs[] }`.

### POST /api/sd/working/single

주문 1건 설계.

\```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"K01","orderNo":"ORD20260510001"}' \
  'http://localhost:8080/api/sd/working/single'
\```

응답: `SingleDesignResponse { slabResults[], errorCode, errorMessage, trace }`.

### POST /api/sd/working/single?trace=true

위와 동일 + step-별 trace 반환. **시뮬레이션 검증 정답 인터페이스**.

\```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"K01","orderNo":"ORD20260510001"}' \
  'http://localhost:8080/api/sd/working/single?trace=true' | python3 -m json.tool
\```

`trace`의 각 row 스키마: `{ step, stepName, phase, iteration, input, output, status, errorCode, errorMessage }`.

`phase ∈ { ONE_SHOT, AA_LOOP, FINAL, SAVE, VALIDATION }`.
`status ∈ { OK, RETRY, FAIL, SKIP }`.

## 2. 주문 (Orders)

### GET /api/sd/orders?cmpCd=&orgCd=&page=&size=
시드된 주문 목록.

### GET /api/sd/orders/{cmpCd}/{orgCd}/{orderNo}
주문 1건 상세 (4 ORDER_* 조인).

## 3. 결과 (Results)

### GET /api/sd/results?cmpCd=&orgCd=&orderNo=
주문에 대한 슬랩 결과들.

### GET /api/sd/results/{slabNo}
12-digit slabNo로 슬랩 1건 조회.

## 4. 이력 (History)

### GET /api/sd/history?cmpCd=&orgCd=&orderNo=
21-step 설계 history (각 step별 row).

## 5. 시드 (Seed)

### POST /api/sd/seed/reset
DB 리셋 + 시드 재실행. 응답 `{ ok: true, scenarios: ["S1",...,"S5"] }`.

### GET /api/sd/seed/scenarios
5개 시나리오 메타 (ID + 주문번호 + description + 예상 결과).
```

- [ ] **Step 2: Commit**

```bash
git add sample-repos/slab-design-real_v2/docs/API.md
git commit -m "docs(slab-v2): API.md with curl examples"
```

---

### Task 10.3: SCENARIOS.md + V1_TO_V2_DIFF.md

**Files:**
- Create: `V2/docs/SCENARIOS.md`
- Create: `V2/docs/V1_TO_V2_DIFF.md`

- [ ] **Step 1: SCENARIOS.md**

```markdown
# 5개 골든 시나리오

| ID | 주문번호 | confirmedPlantCd | 활성 공정 | 의도 / 예상 결과 |
|----|---------|-------------------|----------|----------------|
| S1 | ORD20260510001 | `K   K   ` | SM, CR | 일반 COIL 골든 패스. 슬랩 1매. trace 21 step OK. |
| S2 | ORD20260510002 | `KK      ` | SM, HR | 큰 주문 (50t) → maxSplitCount=4. 슬랩 4매. |
| S3 | ORD20260510003 | `KKKK    ` | SM, HR, HRF, CR | A-a loop 첫 시도 fail → splitCount-1로 재진입 후 성공. trace에 step 12-13 RETRY + iteration=2 OK. |
| S4 | ORD20260510004 | `KK      ` | SM, HR | CUST-FAIL의 packagingWgtHigh=200 < 설계대기량 → DG004. errorCode=DG004, slabResults []. |
| S5 | ORD20260510005 | `K      K` | SM, CRF | 6 공정 비활성 → 누적실수율 = SM × CRF만 곱. 슬랩 1매. |

## 시드 데이터 출처

합성 (`v1`의 도메인 글로서리 기반 합리적 값). 실제 운영 데이터 아님.
- 강종: SS400, SS41
- 폭: 800-1500mm
- 단중: 4000-15000kg
- 회사·소: K, K01

## 골든 검증 매커니즘

1. `GOLDEN_REGEN=true ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest` → trace JSON 캡처
2. 사람이 manual 검토 (위 표의 예상 결과와 일치 확인)
3. 통과 → `src/test/resources/golden/S{1..5}.json` 으로 fix
4. 이후 알고리즘 변경: 의도면 골든 재생성, 의도 외면 회귀로 잡힘

## Volatile 필드 (비교 제외)

- `trace[].elapsedMs` (timing)
- `slabResults[].slabNo` (sequence)
- `slabResults[].createdAt` (timestamp)
```

- [ ] **Step 2: V1_TO_V2_DIFF.md**

```markdown
# v1 → v2 차이 매핑

## 보존 (절대 안 건드림)

- 21-step 알고리즘 순서 / 산출 결과
- DG001-005 / DG101-109 에러 코드 의미론
- 8-char `confirmedPlantCd` 위치 인코딩
- 누적 실수율 곱 공식
- EDGING `*` wildcard fallback
- `_1` suffix 컬럼 (SLAB_RESULT.TARGET_WIDTH_1, TARGET_LENGTH_1, SLAB_WGT_1)
- 12-digit zero-padded slabNo

## 변경 (drama DNA 청소)

| 영역 | v1 | v2 |
|------|-----|-----|
| 비표준 컬럼명 | PRODUCT_TYPE_CD / NAME_CD / KIND_CD 혼재 | PRODUCT_CD 통일 |
| Magic number | 0.95, 7.82, 999999.999 코드 곳곳 | SdConstants 상수 |
| Reflection 매핑 | SDOrderLogic Field.get/set | 명시적 setter 호출 |
| 4+ level nested if | early-return / 가드절 | 행동 동일 |
| @author 김XX (YYYY-MM-DD) | 곳곳 | 제거 |
| 주석 처리 코드 블록 | 곳곳 | 제거 |
| 패키지 `oracle.{jpo,repository}` | DB 종속 segment | `{jpo,repository}` (segment 제거) |

## 인프라 변경

| 영역 | v1 | v2 |
|------|-----|-----|
| DB | Oracle (placeholder) | H2 in-memory (MODE=Oracle) |
| Schema | DDL 없음 | JPA `ddl-auto: create-drop` |
| Seed | 없음 | `db/seed/01_master.sql`, `02_orders.sql` 5 시나리오 |
| Kafka | 의존성 / config 존재 (미연결) | 제거 |
| MyBatis | 의존성 (미사용) | 제거 |
| Swagger | 없음 | springdoc-openapi UI |
| 테스트 | 없음 | JUnit 5 + Mockito + AssertJ + RestAssured 3-tier |
| API endpoint | POST /batch (1개 동작) | 10개 (batch + single + trace + orders + results + history + seed) |

## 새로 추가된 기능

- TraceCollector + StepTrace : 시뮬레이션 검증 정답 인터페이스
- POST /api/sd/seed/reset : DB 깨끗하게 + 시드 재실행
- GET /api/sd/seed/scenarios : 5 시나리오 메타 + 골든
- POST /api/sd/working/single?trace=true : step-별 입출력 JSON
```

- [ ] **Step 3: Commit**

```bash
git add sample-repos/slab-design-real_v2/docs/SCENARIOS.md sample-repos/slab-design-real_v2/docs/V1_TO_V2_DIFF.md
git commit -m "docs(slab-v2): SCENARIOS + V1_TO_V2_DIFF"
```

---

## Phase 11 — Final Verification (DoD per SPEC §8)

### Task 11.1: Definition-of-Done checklist

- [ ] **Step 1: `./mvnw clean verify` BUILD SUCCESS**

```bash
cd /Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real_v2
./mvnw clean verify
```
Expected: BUILD SUCCESS, all 3 test tiers pass.

- [ ] **Step 2: Server starts cleanly**

```bash
./mvnw spring-boot:run -pl slab-design-boot &
SERVER_PID=$!
sleep 30
curl -sf http://localhost:8080/actuator/health 2>/dev/null || curl -sf http://localhost:8080/swagger-ui.html > /dev/null && echo "server OK"
kill $SERVER_PID
```

- [ ] **Step 3: Verify v1 untouched**

```bash
git status sample-repos/slab-design-real/
```
Expected: no changes (clean).

- [ ] **Step 4: Verify other onTong areas untouched**

```bash
git status backend/ frontend/ data/ scripts/ toClaude/
```
Expected: only files that were modified at session start (already in git status), no new modifications from v2 work.

- [ ] **Step 5: External dependencies**

Confirm only Java 21 was needed. No Docker, no Oracle XE, no Kafka. Maven Wrapper handled mvn invocation.

- [ ] **Step 6: Final commit (if anything outstanding)**

```bash
git status
# if anything: 
git add ...
git commit -m "chore(slab-v2): final cleanup"
```

---

## Self-Review Checklist (executed before publishing this plan)

**1. Spec coverage:**
- §3 project structure → Phase 1 (Tasks 1.1-1.4)
- §4 data layer → Phase 2-3, Phase 8 (seeds)
- §5 API surface → Phase 7 (Tasks 7.1-7.6)
- §5.4 trace → Phase 6 (Task 6.1-6.2)
- §6 test strategy → Phase 5 (Tier 1 unit), Phase 2 Task 2.5 (Tier 2 baseline), Phase 9 (Tier 3 golden)
- §7 drama DNA cleanup → blanket pass embedded in Phase 2-5 copy tasks
- §8 DoD → Phase 11

**2. Placeholder scan:**
- Task 5.2 step 2 says "Replicate pattern" — this is acceptable because the test pattern is fully shown in step 1 and the action shapes are the engineer's read of v2 files. Not a placeholder failure.
- Task 6.2 step 5 has a `buildHappyPathDesigner` `// TODO inline mocks` — this is intentional because end-to-end coverage is in Phase 9 golden tests. Marked with @Disabled instructions. Acceptable.
- All other steps include exact code, commands, or specific edit instructions.

**3. Type consistency:**
- `TraceCollector.wrap` returns `T` and accepts `Supplier<T>` — used same way in Designer (Task 6.2).
- `SingleDesignResponse.okWithTrace(slabs, traces)` matches `collector.traces()` return type `List<StepTrace>`.
- `SDOrderEntity` field naming uses `productCd` consistently after rename.

**4. Ambiguity:**
- "Apply blanket renames" tasks are explicit about which renames to apply. The engineer reads each file, applies the listed substitutions.
- "Adjust based on actual signature" notes appear when v1 file shape varies per action — this is necessary; the engineer must read v1 to write the corresponding test, but the structure is given.

No issues found requiring inline fix beyond what's already in the plan.
