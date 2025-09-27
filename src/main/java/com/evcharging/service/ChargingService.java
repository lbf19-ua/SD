package com.evcharging.service;

import com.evcharging.model.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Core service for managing EV charging operations
 */
public class ChargingService {
    private Map<String, ChargingStation> stations;
    private Map<String, Vehicle> vehicles;
    private Map<String, ChargingSession> activeSessions;
    private Map<String, ChargingSession> completedSessions;
    private int sessionCounter;
    
    public ChargingService() {
        this.stations = new ConcurrentHashMap<>();
        this.vehicles = new ConcurrentHashMap<>();
        this.activeSessions = new ConcurrentHashMap<>();
        this.completedSessions = new ConcurrentHashMap<>();
        this.sessionCounter = 0;
    }
    
    // Station management
    public void registerStation(ChargingStation station) {
        stations.put(station.getId(), station);
        System.out.println("Registered charging station: " + station);
    }
    
    public ChargingStation getStation(String stationId) {
        return stations.get(stationId);
    }
    
    public List<ChargingStation> getAllStations() {
        return new ArrayList<>(stations.values());
    }
    
    public List<ChargingStation> getAvailableStations() {
        return stations.values().stream()
                .filter(station -> station.isOperational() && station.hasAvailablePort())
                .collect(ArrayList::new, (list, station) -> list.add(station), ArrayList::addAll);
    }
    
    // Vehicle management
    public void registerVehicle(Vehicle vehicle) {
        vehicles.put(vehicle.getId(), vehicle);
        System.out.println("Registered vehicle: " + vehicle);
    }
    
    public Vehicle getVehicle(String vehicleId) {
        return vehicles.get(vehicleId);
    }
    
    // Charging session management
    public String startChargingSession(String vehicleId, String stationId) {
        Vehicle vehicle = vehicles.get(vehicleId);
        ChargingStation station = stations.get(stationId);
        
        if (vehicle == null) {
            throw new IllegalArgumentException("Vehicle not found: " + vehicleId);
        }
        
        if (station == null) {
            throw new IllegalArgumentException("Station not found: " + stationId);
        }
        
        if (!station.isOperational()) {
            throw new IllegalStateException("Station is not operational: " + stationId);
        }
        
        ChargingPort availablePort = station.getAvailablePort();
        if (availablePort == null) {
            throw new IllegalStateException("No available ports at station: " + stationId);
        }
        
        // Connect vehicle to port
        availablePort.connectVehicle(vehicle);
        
        // Create charging session
        String sessionId = "SESSION_" + (++sessionCounter);
        ChargingSession session = new ChargingSession(sessionId, vehicle, availablePort);
        activeSessions.put(sessionId, session);
        
        System.out.println("Started charging session: " + session);
        return sessionId;
    }
    
    public void chargeVehicle(String sessionId, int targetCharge) {
        ChargingSession session = activeSessions.get(sessionId);
        if (session == null) {
            throw new IllegalArgumentException("Session not found: " + sessionId);
        }
        
        Vehicle vehicle = session.getVehicle();
        int currentCharge = vehicle.getCurrentCharge();
        
        if (currentCharge >= targetCharge) {
            System.out.println("Vehicle already at or above target charge: " + currentCharge + "%");
            return;
        }
        
        // Simulate charging process
        System.out.println("Charging vehicle " + vehicle.getId() + " from " + currentCharge + "% to " + targetCharge + "%...");
        vehicle.setCurrentCharge(targetCharge);
        System.out.println("Charging completed. Vehicle now at " + targetCharge + "%");
    }
    
    public void endChargingSession(String sessionId) {
        ChargingSession session = activeSessions.remove(sessionId);
        if (session == null) {
            throw new IllegalArgumentException("Session not found: " + sessionId);
        }
        
        // Disconnect vehicle from port
        session.getPort().disconnectVehicle();
        
        // Complete the session
        session.completeSession();
        completedSessions.put(sessionId, session);
        
        System.out.println("Ended charging session: " + session);
    }
    
    public ChargingSession getActiveSession(String sessionId) {
        return activeSessions.get(sessionId);
    }
    
    public List<ChargingSession> getActiveSessions() {
        return new ArrayList<>(activeSessions.values());
    }
    
    public List<ChargingSession> getCompletedSessions() {
        return new ArrayList<>(completedSessions.values());
    }
    
    // Utility methods
    public void printSystemStatus() {
        System.out.println("\n=== EV Charging System Status ===");
        System.out.println("Registered Stations: " + stations.size());
        stations.values().forEach(System.out::println);
        
        System.out.println("\nRegistered Vehicles: " + vehicles.size());
        vehicles.values().forEach(System.out::println);
        
        System.out.println("\nActive Sessions: " + activeSessions.size());
        activeSessions.values().forEach(System.out::println);
        
        System.out.println("================================\n");
    }
}