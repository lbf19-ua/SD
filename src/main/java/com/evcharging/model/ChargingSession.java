package com.evcharging.model;

import java.time.LocalDateTime;

/**
 * Represents a charging session for a vehicle at a charging port
 */
public class ChargingSession {
    private String id;
    private Vehicle vehicle;
    private ChargingPort port;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private int initialCharge;
    private int finalCharge;
    private double energyConsumed; // kWh
    private SessionStatus status;
    
    public enum SessionStatus {
        ACTIVE, COMPLETED, CANCELLED, ERROR
    }
    
    public ChargingSession(String id, Vehicle vehicle, ChargingPort port) {
        this.id = id;
        this.vehicle = vehicle;
        this.port = port;
        this.startTime = LocalDateTime.now();
        this.initialCharge = vehicle.getCurrentCharge();
        this.status = SessionStatus.ACTIVE;
        this.energyConsumed = 0.0;
    }
    
    public String getId() { return id; }
    public Vehicle getVehicle() { return vehicle; }
    public ChargingPort getPort() { return port; }
    public LocalDateTime getStartTime() { return startTime; }
    public LocalDateTime getEndTime() { return endTime; }
    public int getInitialCharge() { return initialCharge; }
    public int getFinalCharge() { return finalCharge; }
    public double getEnergyConsumed() { return energyConsumed; }
    public SessionStatus getStatus() { return status; }
    
    public void completeSession() {
        this.endTime = LocalDateTime.now();
        this.finalCharge = vehicle.getCurrentCharge();
        this.energyConsumed = calculateEnergyConsumed();
        this.status = SessionStatus.COMPLETED;
    }
    
    public void cancelSession() {
        this.endTime = LocalDateTime.now();
        this.finalCharge = vehicle.getCurrentCharge();
        this.status = SessionStatus.CANCELLED;
    }
    
    private double calculateEnergyConsumed() {
        int chargeIncrease = finalCharge - initialCharge;
        return (chargeIncrease / 100.0) * vehicle.getBatteryCapacity();
    }
    
    @Override
    public String toString() {
        return String.format("ChargingSession{id='%s', vehicle='%s', status=%s, %d%%->%d%%}", 
                           id, vehicle.getId(), status, initialCharge, 
                           status == SessionStatus.ACTIVE ? vehicle.getCurrentCharge() : finalCharge);
    }
}