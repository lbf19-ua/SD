package com.evcharging.model;

import java.util.ArrayList;
import java.util.List;

/**
 * Represents a charging station with multiple charging ports
 */
public class ChargingStation {
    private String id;
    private String location;
    private List<ChargingPort> ports;
    private boolean isOperational;
    
    public ChargingStation(String id, String location, int numberOfPorts) {
        this.id = id;
        this.location = location;
        this.ports = new ArrayList<>();
        this.isOperational = true;
        
        // Initialize charging ports
        for (int i = 1; i <= numberOfPorts; i++) {
            ports.add(new ChargingPort(id + "_PORT_" + i, 50)); // 50kW charging power
        }
    }
    
    public String getId() { return id; }
    public String getLocation() { return location; }
    public List<ChargingPort> getPorts() { return ports; }
    public boolean isOperational() { return isOperational; }
    public void setOperational(boolean operational) { this.isOperational = operational; }
    
    public boolean hasAvailablePort() {
        return ports.stream().anyMatch(port -> port.isAvailable());
    }
    
    public ChargingPort getAvailablePort() {
        return ports.stream()
                   .filter(ChargingPort::isAvailable)
                   .findFirst()
                   .orElse(null);
    }
    
    public int getAvailablePortCount() {
        return (int) ports.stream().filter(ChargingPort::isAvailable).count();
    }
    
    @Override
    public String toString() {
        return String.format("ChargingStation{id='%s', location='%s', available=%d/%d}", 
                           id, location, getAvailablePortCount(), ports.size());
    }
}