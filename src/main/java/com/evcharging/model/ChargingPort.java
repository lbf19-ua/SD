package com.evcharging.model;

/**
 * Represents a single charging port within a charging station
 */
public class ChargingPort {
    private String id;
    private int maxPowerKw; // Maximum charging power in kW
    private boolean isAvailable;
    private Vehicle currentVehicle;
    
    public ChargingPort(String id, int maxPowerKw) {
        this.id = id;
        this.maxPowerKw = maxPowerKw;
        this.isAvailable = true;
        this.currentVehicle = null;
    }
    
    public String getId() { return id; }
    public int getMaxPowerKw() { return maxPowerKw; }
    public boolean isAvailable() { return isAvailable; }
    public Vehicle getCurrentVehicle() { return currentVehicle; }
    
    public boolean connectVehicle(Vehicle vehicle) {
        if (!isAvailable) {
            return false;
        }
        
        this.currentVehicle = vehicle;
        this.isAvailable = false;
        return true;
    }
    
    public Vehicle disconnectVehicle() {
        Vehicle vehicle = this.currentVehicle;
        this.currentVehicle = null;
        this.isAvailable = true;
        return vehicle;
    }
    
    @Override
    public String toString() {
        return String.format("ChargingPort{id='%s', power=%dkW, available=%s}", 
                           id, maxPowerKw, isAvailable);
    }
}