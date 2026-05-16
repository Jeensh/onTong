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
