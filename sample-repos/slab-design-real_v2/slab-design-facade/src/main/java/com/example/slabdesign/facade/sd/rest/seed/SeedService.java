package com.example.slabdesign.facade.sd.rest.seed;

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

    private final DataSource dataSource;
    private final ResourceLoader resourceLoader;

    /** Order matters for FK awareness, but H2 handles this with REFERENTIAL_INTEGRITY toggle. */
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
                } catch (Exception e) {
                    // table absent → skip silently (defensive for partial schema states)
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
