package com.evcharging.client;

import com.evcharging.model.*;
import com.evcharging.service.ChargingService;
import java.util.Scanner;

/**
 * Interactive CLI client for the EV Charging System
 */
public class EVChargingClient {
    private ChargingService chargingService;
    private Scanner scanner;
    
    public EVChargingClient() {
        this.chargingService = new ChargingService();
        this.scanner = new Scanner(System.in);
        initializeSystem();
    }
    
    private void initializeSystem() {
        // Initialize with some sample data
        ChargingStation station1 = new ChargingStation("STATION_001", "Mall Plaza", 4);
        ChargingStation station2 = new ChargingStation("STATION_002", "City Center", 2);
        chargingService.registerStation(station1);
        chargingService.registerStation(station2);
        
        Vehicle tesla = new Vehicle("TESLA_001", "user1", "Tesla", "Model 3", 75);
        Vehicle nissan = new Vehicle("NISSAN_001", "user2", "Nissan", "Leaf", 40);
        tesla.setCurrentCharge(20);
        nissan.setCurrentCharge(15);
        
        chargingService.registerVehicle(tesla);
        chargingService.registerVehicle(nissan);
    }
    
    public void start() {
        System.out.println("=== EV Charging System CLI ===");
        System.out.println("Welcome to the EV Charging Management System");
        
        boolean running = true;
        while (running) {
            showMenu();
            int choice = getChoice();
            
            try {
                switch (choice) {
                    case 1:
                        showSystemStatus();
                        break;
                    case 2:
                        listStations();
                        break;
                    case 3:
                        listVehicles();
                        break;
                    case 4:
                        startCharging();
                        break;
                    case 5:
                        listActiveSessions();
                        break;
                    case 6:
                        endCharging();
                        break;
                    case 7:
                        registerNewVehicle();
                        break;
                    case 8:
                        listCompletedSessions();
                        break;
                    case 0:
                        running = false;
                        System.out.println("Goodbye!");
                        break;
                    default:
                        System.out.println("Invalid option. Please try again.");
                }
            } catch (Exception e) {
                System.err.println("Error: " + e.getMessage());
            }
            
            if (running) {
                System.out.println("\nPress Enter to continue...");
                scanner.nextLine();
            }
        }
    }
    
    private void showMenu() {
        System.out.println("\n=== Main Menu ===");
        System.out.println("1. Show System Status");
        System.out.println("2. List Charging Stations");
        System.out.println("3. List Vehicles");
        System.out.println("4. Start Charging Session");
        System.out.println("5. List Active Sessions");
        System.out.println("6. End Charging Session");
        System.out.println("7. Register New Vehicle");
        System.out.println("8. List Completed Sessions");
        System.out.println("0. Exit");
        System.out.print("Choose an option: ");
    }
    
    private int getChoice() {
        try {
            return Integer.parseInt(scanner.nextLine().trim());
        } catch (NumberFormatException e) {
            return -1;
        }
    }
    
    private void showSystemStatus() {
        chargingService.printSystemStatus();
    }
    
    private void listStations() {
        System.out.println("\n=== Charging Stations ===");
        chargingService.getAllStations().forEach(System.out::println);
    }
    
    private void listVehicles() {
        System.out.println("\n=== Registered Vehicles ===");
        chargingService.getAllStations().forEach(station -> {
            // This is a simplified approach - in a real system you'd have a proper vehicle registry
        });
        System.out.println("TESLA_001: Tesla Model 3 (75kWh)");
        System.out.println("NISSAN_001: Nissan Leaf (40kWh)");
    }
    
    private void startCharging() {
        System.out.print("Enter Vehicle ID: ");
        String vehicleId = scanner.nextLine().trim();
        System.out.print("Enter Station ID: ");
        String stationId = scanner.nextLine().trim();
        
        String sessionId = chargingService.startChargingSession(vehicleId, stationId);
        System.out.println("Charging session started: " + sessionId);
        
        System.out.print("Enter target charge percentage (0-100): ");
        int targetCharge = Integer.parseInt(scanner.nextLine().trim());
        chargingService.chargeVehicle(sessionId, targetCharge);
    }
    
    private void listActiveSessions() {
        System.out.println("\n=== Active Charging Sessions ===");
        chargingService.getActiveSessions().forEach(System.out::println);
    }
    
    private void endCharging() {
        System.out.print("Enter Session ID: ");
        String sessionId = scanner.nextLine().trim();
        chargingService.endChargingSession(sessionId);
        System.out.println("Charging session ended: " + sessionId);
    }
    
    private void registerNewVehicle() {
        System.out.print("Enter Vehicle ID: ");
        String id = scanner.nextLine().trim();
        System.out.print("Enter Owner ID: ");
        String ownerId = scanner.nextLine().trim();
        System.out.print("Enter Make: ");
        String make = scanner.nextLine().trim();
        System.out.print("Enter Model: ");
        String model = scanner.nextLine().trim();
        System.out.print("Enter Battery Capacity (kWh): ");
        int capacity = Integer.parseInt(scanner.nextLine().trim());
        
        Vehicle vehicle = new Vehicle(id, ownerId, make, model, capacity);
        chargingService.registerVehicle(vehicle);
    }
    
    private void listCompletedSessions() {
        System.out.println("\n=== Completed Sessions ===");
        chargingService.getCompletedSessions().forEach(System.out::println);
    }
    
    public static void main(String[] args) {
        new EVChargingClient().start();
    }
}