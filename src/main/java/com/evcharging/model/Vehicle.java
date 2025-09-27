package com.evcharging.model;

/**
 * Represents an electric vehicle that can be charged at charging stations
 */
public class Vehicle {
    private String id;
    private String ownerId;
    private String make;
    private String model;
    private int batteryCapacity; // in kWh
    private int currentCharge; // percentage (0-100)
    
    public Vehicle(String id, String ownerId, String make, String model, int batteryCapacity) {
        this.id = id;
        this.ownerId = ownerId;
        this.make = make;
        this.model = model;
        this.batteryCapacity = batteryCapacity;
        this.currentCharge = 0;
    }
    
    // Getters and setters
    public String getId() { return id; }
    public String getOwnerId() { return ownerId; }
    public String getMake() { return make; }
    public String getModel() { return model; }
    public int getBatteryCapacity() { return batteryCapacity; }
    public int getCurrentCharge() { return currentCharge; }
    public void setCurrentCharge(int currentCharge) { 
        this.currentCharge = Math.max(0, Math.min(100, currentCharge)); 
    }
    
    public boolean needsCharging() {
        return currentCharge < 80; // Consider vehicle needs charging if below 80%
    }
    
    @Override
    public String toString() {
        return String.format("Vehicle{id='%s', make='%s', model='%s', charge=%d%%}", 
                           id, make, model, currentCharge);
    }
}