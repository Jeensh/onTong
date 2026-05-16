package com.example.slabdesign.store;

import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

/**
 * Minimal Spring Boot test configuration for the store module.
 *
 * <p>The store module is a library (no {@code @SpringBootApplication}),
 * so {@code @DataJpaTest} cannot bootstrap on its own. This class provides
 * a {@code @SpringBootConfiguration} root for tests, plus {@code @EntityScan}
 * and {@code @EnableJpaRepositories} so JPA entities and repositories
 * across all sd subpackages (std, working, history, analysis) are picked up.
 */
@SpringBootConfiguration
@EnableAutoConfiguration
@ComponentScan(basePackages = "com.example.slabdesign.store")
@EntityScan(basePackages = "com.example.slabdesign.store")
@EnableJpaRepositories(basePackages = "com.example.slabdesign.store")
public class StoreTestConfig {
}
