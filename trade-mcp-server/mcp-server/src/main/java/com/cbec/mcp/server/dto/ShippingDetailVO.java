package com.cbec.mcp.server.dto;

import lombok.Data;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 物流详情视图，包含物流概况与时间线轨迹列表。
 */
@Data
public class ShippingDetailVO {
    private Long shippingId;
    private String orderNo;
    private String trackingNo;
    private String carrier;
    private String shippingMethod;
    private String originPort;
    private String destinationPort;
    private LocalDate estimatedDeparture;
    private LocalDate actualDeparture;
    private LocalDate estimatedArrival;
    private LocalDate actualArrival;
    private String customsStatus;
    private String shippingStatus;
    private String packageInfo;
    private List<TrackRecord> tracks;

    @Data
    public static class TrackRecord {
        private LocalDateTime trackTime;
        private String location;
        private String status;
        private String description;
    }
}
