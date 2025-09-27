# SD - Distributed Systems 2025
Practicas SD 2025

## Practica 1: EVCharging System

A distributed Electric Vehicle (EV) charging management system implemented in Java. This system demonstrates key distributed systems concepts including resource management, concurrent operations, and service orchestration.

### Features

- **Charging Station Management**: Register and manage multiple charging stations with configurable number of ports
- **Vehicle Registration**: Support for various EV models with different battery capacities
- **Charging Session Management**: Track charging sessions from start to completion
- **Resource Allocation**: Automatic port assignment and availability management
- **Concurrent Operations**: Thread-safe operations for multiple simultaneous charging sessions

### System Architecture

The system consists of several key components:

- **Model Layer**: Core domain objects (Vehicle, ChargingStation, ChargingPort, ChargingSession)
- **Service Layer**: Business logic for managing charging operations (ChargingService)
- **Client Layer**: Command-line interface for system interaction (EVChargingClient)

### Quick Start

#### Prerequisites
- Java 11 or higher
- Maven 3.6 or higher

#### Building the Project
```bash
mvn clean compile
```

#### Running Tests
```bash
mvn test
```

#### Running the Demo
```bash
mvn exec:java -Dexec.mainClass="com.evcharging.EVChargingSystem"
```

#### Running the Interactive CLI
```bash
mvn exec:java -Dexec.mainClass="com.evcharging.client.EVChargingClient"
```

### Usage Examples

#### Basic Demo Scenario
The main demo showcases:
1. Registration of charging stations with multiple ports
2. Registration of various EV models
3. Starting multiple charging sessions simultaneously
4. Managing charging operations
5. Completing and tracking charging sessions

#### Interactive CLI
The CLI client provides the following operations:
- View system status
- List available charging stations
- Register new vehicles
- Start/end charging sessions
- Monitor active and completed sessions

### Project Structure
```
src/
├── main/java/com/evcharging/
│   ├── model/              # Domain models
│   │   ├── Vehicle.java
│   │   ├── ChargingStation.java
│   │   ├── ChargingPort.java
│   │   └── ChargingSession.java
│   ├── service/            # Business logic
│   │   └── ChargingService.java
│   ├── client/             # Client interfaces
│   │   └── EVChargingClient.java
│   └── EVChargingSystem.java   # Main application
└── test/java/com/evcharging/
    └── service/
        └── ChargingServiceTest.java
```

### Key Distributed Systems Concepts Demonstrated

1. **Resource Management**: Efficient allocation of charging ports across multiple stations
2. **Concurrency Control**: Thread-safe operations using concurrent data structures
3. **Session Management**: Stateful tracking of long-running operations
4. **Service Orchestration**: Coordination between multiple system components
5. **Error Handling**: Graceful handling of resource conflicts and invalid operations

### Future Enhancements

This system can be extended to include:
- Network communication between distributed stations
- Load balancing across charging networks
- Real-time monitoring and alerts
- Payment processing integration
- Energy grid optimization
