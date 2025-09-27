package com.evcharging.service;

import com.evcharging.model.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for ChargingService
 */
public class ChargingServiceTest {
    private ChargingService chargingService;
    private ChargingStation testStation;
    private Vehicle testVehicle;
    
    @BeforeEach
    void setUp() {
        chargingService = new ChargingService();
        testStation = new ChargingStation("TEST_STATION", "Test Location", 2);
        testVehicle = new Vehicle("TEST_VEHICLE", "test_user", "Test", "Model", 50);
        testVehicle.setCurrentCharge(20);
        
        chargingService.registerStation(testStation);
        chargingService.registerVehicle(testVehicle);
    }
    
    @Test
    void testRegisterStation() {
        ChargingStation newStation = new ChargingStation("NEW_STATION", "New Location", 3);
        chargingService.registerStation(newStation);
        
        assertEquals(newStation, chargingService.getStation("NEW_STATION"));
        assertEquals(2, chargingService.getAllStations().size());
    }
    
    @Test
    void testRegisterVehicle() {
        Vehicle newVehicle = new Vehicle("NEW_VEHICLE", "new_user", "New", "Car", 60);
        chargingService.registerVehicle(newVehicle);
        
        assertEquals(newVehicle, chargingService.getVehicle("NEW_VEHICLE"));
    }
    
    @Test
    void testStartChargingSession() {
        String sessionId = chargingService.startChargingSession("TEST_VEHICLE", "TEST_STATION");
        
        assertNotNull(sessionId);
        assertTrue(sessionId.startsWith("SESSION_"));
        
        ChargingSession session = chargingService.getActiveSession(sessionId);
        assertNotNull(session);
        assertEquals(testVehicle, session.getVehicle());
        assertEquals(ChargingSession.SessionStatus.ACTIVE, session.getStatus());
    }
    
    @Test
    void testStartChargingSessionWithInvalidVehicle() {
        assertThrows(IllegalArgumentException.class, () -> {
            chargingService.startChargingSession("INVALID_VEHICLE", "TEST_STATION");
        });
    }
    
    @Test
    void testStartChargingSessionWithInvalidStation() {
        assertThrows(IllegalArgumentException.class, () -> {
            chargingService.startChargingSession("TEST_VEHICLE", "INVALID_STATION");
        });
    }
    
    @Test
    void testChargeVehicle() {
        String sessionId = chargingService.startChargingSession("TEST_VEHICLE", "TEST_STATION");
        int initialCharge = testVehicle.getCurrentCharge();
        
        chargingService.chargeVehicle(sessionId, 80);
        
        assertEquals(80, testVehicle.getCurrentCharge());
        assertTrue(testVehicle.getCurrentCharge() > initialCharge);
    }
    
    @Test
    void testEndChargingSession() {
        String sessionId = chargingService.startChargingSession("TEST_VEHICLE", "TEST_STATION");
        chargingService.chargeVehicle(sessionId, 75);
        
        chargingService.endChargingSession(sessionId);
        
        assertNull(chargingService.getActiveSession(sessionId));
        assertEquals(1, chargingService.getCompletedSessions().size());
        
        ChargingSession completedSession = chargingService.getCompletedSessions().get(0);
        assertEquals(ChargingSession.SessionStatus.COMPLETED, completedSession.getStatus());
    }
    
    @Test
    void testGetAvailableStations() {
        // Initially, station should be available
        assertEquals(1, chargingService.getAvailableStations().size());
        
        // Start charging sessions to fill all ports
        chargingService.startChargingSession("TEST_VEHICLE", "TEST_STATION");
        Vehicle vehicle2 = new Vehicle("TEST_VEHICLE_2", "user2", "Test", "Model2", 40);
        chargingService.registerVehicle(vehicle2);
        chargingService.startChargingSession("TEST_VEHICLE_2", "TEST_STATION");
        
        // Now station should have no available ports
        assertTrue(chargingService.getAvailableStations().isEmpty());
    }
}