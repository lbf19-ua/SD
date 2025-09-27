package com.evcharging;

import com.evcharging.model.*;
import com.evcharging.service.ChargingService;

/**
 * Main application class for the EV Charging System
 * Practica 1 - Distributed Systems
 */
public class EVChargingSystem {
    
    public static void main(String[] args) {
        System.out.println("=== EV Charging System - Practica 1 SD ===\n");
        
        // Initialize the charging service
        ChargingService chargingService = new ChargingService();
        
        // Demo scenario
        runDemoScenario(chargingService);
    }
    
    private static void runDemoScenario(ChargingService service) {
        System.out.println("Running demo scenario...\n");
        
        // 1. Register charging stations
        ChargingStation station1 = new ChargingStation("STATION_001", "Mall Plaza", 4);
        ChargingStation station2 = new ChargingStation("STATION_002", "City Center", 2);
        service.registerStation(station1);
        service.registerStation(station2);
        
        // 2. Register vehicles
        Vehicle tesla = new Vehicle("TESLA_001", "user1", "Tesla", "Model 3", 75);
        Vehicle nissan = new Vehicle("NISSAN_001", "user2", "Nissan", "Leaf", 40);
        Vehicle bmw = new Vehicle("BMW_001", "user3", "BMW", "iX3", 80);
        
        tesla.setCurrentCharge(20);
        nissan.setCurrentCharge(10);
        bmw.setCurrentCharge(5);
        
        service.registerVehicle(tesla);
        service.registerVehicle(nissan);
        service.registerVehicle(bmw);
        
        // 3. Show initial status
        service.printSystemStatus();
        
        // 4. Start charging sessions
        try {
            String session1 = service.startChargingSession("TESLA_001", "STATION_001");
            String session2 = service.startChargingSession("NISSAN_001", "STATION_001");
            String session3 = service.startChargingSession("BMW_001", "STATION_002");
            
            // 5. Simulate charging
            service.chargeVehicle(session1, 85);
            service.chargeVehicle(session2, 90);
            service.chargeVehicle(session3, 80);
            
            // 6. Show status during charging
            service.printSystemStatus();
            
            // 7. End charging sessions
            service.endChargingSession(session1);
            service.endChargingSession(session2);
            service.endChargingSession(session3);
            
            // 8. Show final status
            service.printSystemStatus();
            
            // 9. Show completed sessions
            System.out.println("=== Completed Sessions ===");
            service.getCompletedSessions().forEach(System.out::println);
            
        } catch (Exception e) {
            System.err.println("Error during demo: " + e.getMessage());
            e.printStackTrace();
        }
        
        System.out.println("\nDemo completed successfully!");
    }
}