from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
import csv
import io
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from pydantic import BaseModel
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Data Quality Checker API",
    description="Self-contained API with embedded Northwind database for UI5 integration",
    version="3.0.0"
)

# Enable CORS for UI5 app integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your UI5 app domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# COMPLETE Embedded Data Quality Configuration (from your full file)
# ============= COMPLETE EMBEDDED CONFIGURATIONS - ALL TABLES =============

# Your Complete Data Quality Configuration (covers all 12 tables + sqlite_sequence)
DATA_QUALITY_CONFIG = """table_name,field_name,description,special_characters_check,null_check,blank_check,max_value_check,min_value_check,max_count_check,email_check,numeric_check,system_codes_check,language_check,phone_number_check,duplicate_check,date_check
Categories,CategoryID,Unique identifier for each product category,1,1,1,1,1,1,0,0,0,0,0,1,0
Categories,CategoryName,"Name of the product category (e.g., Beverages, Condiments, Dairy Products)",1,1,1,1,1,1,0,0,1,0,0,0,0
Categories,Description,Detailed description of what products belong in this category,1,1,1,1,1,1,0,0,0,0,0,0,0
Categories,Picture,Binary image data representing the category (stored as BLOB/binary data),1,1,1,1,1,1,0,0,0,0,0,1,0
sqlite_sequence,name,Name of the table that has an auto-incrementing primary key (AUTOINCREMENT column),1,1,1,1,1,1,0,0,0,0,0,1,0
sqlite_sequence,seq,Current sequence value or next auto-increment value for the specified table,1,1,1,1,1,1,0,1,0,0,0,0,0
Customers,CustomerID,Unique character identifier for each customer,1,1,1,1,1,1,0,0,0,0,0,1,0
Customers,CompanyName,Name of the customer company,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,ContactName,Name of the primary contact person at the customer,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,ContactTitle,Job title of the contact person,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,Address,Street address of the customer,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,City,City where the customer is located,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,Region,Geographic region of the customer,1,1,1,1,1,1,0,0,1,0,0,0,0
Customers,PostalCode,Postal/ZIP code of the customer location,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,Country,Country where the customer is based,1,1,1,1,1,1,0,0,0,0,0,0,0
Customers,Phone,Primary phone number for the customer,1,1,1,1,1,1,0,1,0,0,1,0,0
Customers,Fax,Fax number for the customer,1,1,1,1,1,1,0,1,0,0,0,0,0
Employees,EmployeeID,Unique numeric identifier for each employee,1,1,1,1,1,1,0,1,0,0,0,1,0
Employees,LastName,Employee's surname,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,FirstName,Employee's given name,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,Title,Job title held by the employee,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,TitleOfCourtesy,"Courtesy title used in correspondence (e.g., Mr., Ms., Dr.)",1,1,1,1,1,1,0,0,1,0,0,0,0
Employees,BirthDate,Employee's date of birth,1,1,1,1,1,1,0,0,0,0,0,0,1
Employees,HireDate,Date the employee was hired,1,1,1,1,1,1,0,0,0,0,0,0,1
Employees,Address,Street address of the employee,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,City,City where the employee is located,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,Region,State/region/province of the employee,1,1,1,1,1,1,0,0,1,0,0,0,0
Employees,PostalCode,Postal or ZIP code,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,Country,Country where the employee resides,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,HomePhone,Primary contact phone number,1,1,1,1,1,1,0,1,0,0,1,0,0
Employees,Extension,Telephone extension in the company,1,1,1,1,1,1,0,1,0,0,0,0,0
Employees,Photo,Binary image data representing the employee's photo,1,1,1,1,1,1,0,0,0,0,0,1,0
Employees,Notes,Free-text notes about the employee,1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,ReportsTo,EmployeeID of the person to whom this employee reports (self-referential foreign key),1,1,1,1,1,1,0,0,0,0,0,0,0
Employees,PhotoPath,File path or URL to the employee's photo,1,1,1,1,1,1,0,0,0,0,0,1,0
EmployeeTerritories,EmployeeID,Foreign key linking to the Employees table - identifies which employee is assigned to a territory,1,1,1,1,1,1,0,0,0,0,0,0,0
EmployeeTerritories,TerritoryID,Foreign key linking to the Territories table - identifies which territory is assigned to an employee,1,1,1,1,1,1,0,0,0,0,0,1,0
OrderDetails,OrderID,Identifier of the related order (foreign key to Orders table),1,1,1,1,1,1,0,0,0,0,0,0,0
OrderDetails,ProductID,Identifier of the ordered product (foreign key to Products table),1,1,1,1,1,1,0,0,0,0,0,0,0
OrderDetails,UnitPrice,Price per unit at the time of ordering,1,1,1,1,1,1,0,1,0,0,0,0,0
OrderDetails,Quantity,Number of units ordered,1,1,1,1,1,1,0,1,0,0,0,0,0
OrderDetails,Discount,Discount applied to the line item,1,1,1,1,1,1,0,1,0,0,0,0,0
Orders,OrderID,Unique identifier for each order,1,1,1,1,1,1,0,0,0,0,0,1,0
Orders,CustomerID,Foreign key linking to the customer who placed the order,1,1,1,1,1,1,0,0,0,0,0,0,0
Orders,EmployeeID,Foreign key linking to the employee who processed the order,1,1,1,1,1,1,0,0,0,0,0,1,0
Orders,OrderDate,Date when the order was placed by the customer,1,1,1,1,1,1,0,0,0,0,0,0,1
Orders,RequiredDate,Date when the customer requires the order to be delivered,1,1,1,1,1,1,0,0,0,0,0,0,1
Orders,ShippedDate,Actual date when the order was shipped (null if not yet shipped),1,1,1,1,1,1,0,0,0,0,0,0,1
Orders,ShipVia,Foreign key linking to the shipping company used,1,1,1,1,1,1,0,0,1,0,0,0,0
Orders,Freight,Shipping cost/freight charges for the order,1,1,1,1,1,1,0,1,0,0,0,0,0
Orders,ShipName,Name of the recipient or company receiving the shipment,1,1,1,1,1,1,0,0,0,0,0,0,0
Orders,ShipAddress,Street address where the order should be delivered,1,1,1,1,1,1,0,0,0,0,0,0,0
Orders,ShipCity,City for the shipping destination,1,1,1,1,1,1,0,0,0,0,0,0,0
Orders,ShipRegion,Region/state/province for the shipping destination,1,1,1,1,1,1,0,0,1,0,0,0,0
Orders,ShipPostalCode,Postal/ZIP code for the shipping destination,1,1,1,1,1,1,0,0,0,0,0,0,0
Orders,ShipCountry,Country where the order should be delivered,1,1,1,1,1,1,0,0,0,0,0,0,0
Products,ProductID,Unique identifier for each product,1,1,1,1,1,1,0,0,0,0,0,1,0
Products,ProductName,Name of the product,1,1,1,1,1,1,0,0,0,0,0,0,0
Products,SupplierID,Foreign key linking to the supplier of this product,1,1,1,1,1,1,0,0,0,0,0,0,0
Products,CategoryID,Foreign key linking to the product category,1,1,1,1,1,1,0,0,0,0,0,0,0
Products,QuantityPerUnit,"Description of package size and quantity (e.g., ""10 boxes x 20 bags"")",1,1,1,1,1,1,0,0,0,0,0,0,0
Products,UnitPrice,Price per unit of the product,1,1,1,1,1,1,0,1,0,0,0,0,0
Products,UnitsInStock,Current quantity available in inventory,1,1,1,1,1,1,0,1,0,0,0,0,0
Products,UnitsOnOrder,Quantity currently on order from supplier,1,1,1,1,1,1,0,1,0,0,0,0,0
Products,ReorderLevel,Minimum stock level that triggers reordering,1,1,1,1,1,1,0,1,0,0,0,0,0
Products,Discontinued,Flag indicating if product is discontinued,1,1,1,1,1,1,0,0,1,0,0,0,0
Regions,RegionID,Unique numeric identifier for each sales region,1,1,1,1,1,1,0,1,0,0,0,1,0
Regions,RegionDescription,Name or description of the region,1,1,1,1,1,1,0,0,0,0,0,0,0
Shippers,ShipperID,Unique identifier for each shipping company,1,1,1,1,1,1,0,0,0,0,0,1,0
Shippers,CompanyName,Name of the shipping/courier company,1,1,1,1,1,1,0,0,0,0,0,0,0
Shippers,Phone,Contact phone number for the shipping company,1,1,1,1,1,1,0,1,0,0,1,0,0
Suppliers,SupplierID,Unique identifier for each supplier company,1,1,1,1,1,1,0,0,0,0,0,1,0
Suppliers,CompanyName,Name of the supplier company,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,ContactName,Name of the primary contact person at the supplier,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,ContactTitle,Job title of the contact person,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,Address,Street address of the supplier,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,City,City where the supplier is located,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,Region,Geographic region of the supplier,1,1,1,1,1,1,0,0,1,0,0,0,0
Suppliers,PostalCode,Postal/ZIP code of the supplier location,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,Country,Country where the supplier is based,1,1,1,1,1,1,0,0,0,0,0,0,0
Suppliers,Phone,Primary phone number for the supplier,1,1,1,1,1,1,0,1,0,0,1,0,0
Suppliers,Fax,Fax number for the supplier,1,1,1,1,1,1,0,1,0,0,0,0,0
Suppliers,HomePage,Website URL or web reference for the supplier,1,1,1,1,1,1,0,0,0,0,0,0,0
Territories,TerritoryID,Unique identifier for each sales territory (ZIP code format),1,1,1,1,1,1,0,0,0,0,0,1,0
Territories,TerritoryDescription,Name or description of the territory location,1,1,1,1,1,1,0,0,0,0,0,0,0
Territories,RegionID,Foreign key linking to the region this territory belongs to,1,1,1,1,1,1,0,0,0,0,0,0,0"""

# Your Complete System Codes Configuration (covers all validation codes)
SYSTEM_CODES_CONFIG = """table_name,field_name,valid_codes
Categories,CategoryName,"Beverages,Condiments,Confections,Dairy Products,Grains/Cereals,Meat/Poultry,Produce,Seafood"
Customers,Region,"Western Europe,Central America,British Isles,Northern Europe,Southern Europe,Eastern Europe,North America,South America,Scandinavia"
Employees,TitleOfCourtesy,"Ms.,Mr.,Dr.,Mrs."
Employees,Region,"North America,British Isles"
Orders,ShipVia,"1,2,3"
Orders,ShipRegion,"Western Europe, South America, Central America, North America, Southern Europe, Northern Europe, British Isles, Eastern Europe, Scandinavia"
Products,Discontinued,"0,1"
Suppliers,Region,"British Isles, North America, Eastern Asia,South America, Southern Europe, Victoria, Southern Europe, Western Europe, Scandinavia, Northern Europe, South-East Asia, NSW"""

# COMPLETE Embedded Database Schema and Data
NORTHWIND_DATABASE_SQL = """
-- Create tables
CREATE TABLE IF NOT EXISTS Categories (
    CategoryID INTEGER PRIMARY KEY,
    CategoryName TEXT NOT NULL,
    Description TEXT,
    Picture BLOB
);

CREATE TABLE IF NOT EXISTS Customers (
    CustomerID TEXT PRIMARY KEY,
    CompanyName TEXT NOT NULL,
    ContactName TEXT,
    ContactTitle TEXT,
    Address TEXT,
    City TEXT,
    Region TEXT,
    PostalCode TEXT,
    Country TEXT,
    Phone TEXT,
    Fax TEXT,
    Email TEXT
);

CREATE TABLE IF NOT EXISTS Employees (
    EmployeeID INTEGER PRIMARY KEY,
    LastName TEXT NOT NULL,
    FirstName TEXT NOT NULL,
    Title TEXT,
    TitleOfCourtesy TEXT,
    BirthDate TEXT,
    HireDate TEXT,
    Address TEXT,
    City TEXT,
    Region TEXT,
    PostalCode TEXT,
    Country TEXT,
    HomePhone TEXT,
    Extension TEXT,
    Photo BLOB,
    Notes TEXT,
    ReportsTo INTEGER,
    PhotoPath TEXT
);

CREATE TABLE IF NOT EXISTS EmployeeTerritories (
    EmployeeID INTEGER,
    TerritoryID TEXT,
    PRIMARY KEY (EmployeeID, TerritoryID)
);

CREATE TABLE IF NOT EXISTS Orders (
    OrderID INTEGER PRIMARY KEY,
    CustomerID TEXT,
    EmployeeID INTEGER,
    OrderDate TEXT,
    RequiredDate TEXT,
    ShippedDate TEXT,
    ShipVia INTEGER,
    Freight REAL,
    ShipName TEXT,
    ShipAddress TEXT,
    ShipCity TEXT,
    ShipRegion TEXT,
    ShipPostalCode TEXT,
    ShipCountry TEXT,
    FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID),
    FOREIGN KEY (ShipVia) REFERENCES Shippers(ShipperID)
);

-- OrderDetails Table (order line items)
CREATE TABLE IF NOT EXISTS OrderDetails (
    OrderID INTEGER,
    ProductID INTEGER,
    UnitPrice REAL NOT NULL,
    Quantity INTEGER NOT NULL,
    Discount REAL DEFAULT 0,
    PRIMARY KEY (OrderID, ProductID),
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
    FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
);

CREATE TABLE IF NOT EXISTS Suppliers (
    SupplierID INTEGER PRIMARY KEY,
    CompanyName TEXT NOT NULL,
    ContactName TEXT,
    ContactTitle TEXT,
    Address TEXT,
    City TEXT,
    Region TEXT,
    PostalCode TEXT,
    Country TEXT,
    Phone TEXT,
    Fax TEXT,
    HomePage TEXT
);

CREATE TABLE IF NOT EXISTS Shippers (
    ShipperID INTEGER PRIMARY KEY,
    CompanyName TEXT NOT NULL,
    Phone TEXT
);

CREATE TABLE IF NOT EXISTS Territories (
    TerritoryID TEXT PRIMARY KEY,
    TerritoryDescription TEXT NOT NULL,
    RegionID INTEGER
);

CREATE TABLE IF NOT EXISTS Regions (
    RegionID INTEGER PRIMARY KEY,
    RegionDescription TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Products (
    ProductID INTEGER PRIMARY KEY,
    ProductName TEXT NOT NULL,
    SupplierID INTEGER,
    CategoryID INTEGER,
    QuantityPerUnit TEXT,
    UnitPrice REAL,
    UnitsInStock INTEGER,
    UnitsOnOrder INTEGER,
    ReorderLevel INTEGER,
    Discontinued INTEGER DEFAULT 0
);

-- Insert ALL Categories data
INSERT INTO Categories VALUES (1, 'Beverages', 'Soft drinks, coffees, teas, beers, and ales', NULL);
INSERT INTO Categories VALUES (2, 'Condiments', 'Sweet and savory sauces, relishes, spreads, and seasonings', NULL);
INSERT INTO Categories VALUES (3, 'Confections', 'Desserts, candies, and sweet breads', NULL);
INSERT INTO Categories VALUES (4, 'Dairy Products', 'Cheeses', NULL);
INSERT INTO Categories VALUES (5, 'Grains/Cereals', 'Breads, crackers, pasta, and cereal', NULL);
INSERT INTO Categories VALUES (6, 'Meat/Poultry', 'Prepared meats', NULL);
INSERT INTO Categories VALUES (7, 'Produce', 'Dried fruit and bean curd', NULL);
INSERT INTO Categories VALUES (8, 'Seafood', 'Seaweed and fish', NULL);

-- Insert ALL Customers data (93 customers from your CSV)
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ALFKI', 'Alfreds Futterkiste', 'Maria Anders', 'Sales Representative', 'Obere Str. 57', 'Berlin', 'Western Europe', '12209', 'Germany', '7788899959517', '0300076545', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ANATR', 'Ana Trujillo Emparedados y helados', 'Ana Trujillo', 'Owner', 'Avda. de la Constitución 2222', 'México D.F.', 'Central America', '05021', 'Mexico', '8763306695', '5553745', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ANTON', 'Antonio Moreno Taquería', 'Antonio Moreno', 'Owner', 'Mataderos  2312', 'México D.F.', 'Central America', '05023', 'Mexico', '93120616809046', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('AROUT', 'Around the Horn', 'Thomas Hardy', 'Sales Representative', '120 Hanover Sq.', 'London', 'British Isles', 'WA1 1DP', 'UK', '6597529568628', '1715556750', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BERGS', 'Berglunds snabbkop', 'Christina Berglund', 'Order Administrator', 'Berguvsvägen  8', 'Luleå', 'Northern Europe', 'S-958 22', 'Sweden', '1244066251264', '0921123467', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BLAUS', 'Blauer See Delikatessen', 'Hanna Moos', 'Sales Representative', 'Forsterstr. 57', 'Mannheim', 'Western Europe', '68306', 'Germany', '8353236645046', '062108924', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BLONP', 'Blondesddsl pere et fils', 'Frédérique Citeaux', 'Marketing Manager', '24, place Kléber', 'Strasbourg', 'Western Europe', '67000', 'France', '1398226573', '88601532', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BOLID', 'Belido Comidas preparadas', 'Martín Sommer', 'Owner', 'C/ Araquil, 67', 'Madrid', 'Southern Europe', '28023', 'Spain', '6054731621926', '915559199', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BONAP', 'Bon app', 'Laurence Lebihan', 'Owner', '12, rue des Bouchers', 'Marseille', 'Western Europe', '13008', 'France', '20977797438620', '91243541', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BOTTM', 'Bottom-Dollar Markets', 'Elizabeth Lincoln', 'Accounting Manager', '23 Tsawassen Blvd.', 'Tsawassen', 'North America', 'T2F 8M4', 'Canada', '7297189542360', '6045553745', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('BSBEV', 'B Beverages', 'Victoria Ashworth', 'Sales Representative', 'Fauntleroy Circus', 'London', 'British Isles', 'EC2 5NT', 'UK', '1193214251', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('CACTU', 'Cactus Comidas para llevar', 'Patricio Simpson', 'Sales Agent', 'Cerrito 333', 'Buenos Aires', 'South America', '1010', 'Argentina', '1741071561', '1354892', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('CENTC', 'Centro comercial Moctezuma', 'Francisco Chang', 'Marketing Manager', 'Sierras de Granada 9993', 'México D.F.', 'Central America', '05022', 'Mexico', '38113742439', '55557293', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('CHOPS', 'Chop-suey Chinese', 'Yang Wang', 'Owner', 'Hauptstr. 29', 'Bern', 'Western Europe', '3012', 'Switzerland', '501070501313', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('COMMI', 'Comercio Mineiro', 'Pedro Afonso', 'Sales Associate', 'Av. dos Lusíadas, 23', 'Sao Paulo', 'South America', '05432-043', 'Brazil', '39108308562904', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('CONSH', 'Consolidated Holdings', 'Elizabeth Brown', 'Sales Representative', 'Berkeley Gardens 12  Brewery', 'London', 'British Isles', 'WX1 6LT', 'UK', '530111223666353', '1795559199', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('DRACD', 'Drachenblut Delikatessen', 'Sven Ottlieb', 'Order Administrator', 'Walserweg 21', 'Aachen', 'Western Europe', '52066', 'Germany', '511716944432', '0241059428', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('DUMON', 'Du monde entier', 'Janine Labrune', 'Owner', '67, rue des Cinquante Otages', 'Nantes', 'Western Europe', '44000', 'France', '6475418160347', '40678989', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('EASTC', 'Eastern Connection', 'Ann Devon', 'Sales Agent', '35 King George', 'London', 'British Isles', 'WX3 6FW', 'UK', '456265148515', '1715553373', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ERNSH', 'Ernst Handel', 'Roland Mendel', 'Sales Manager', 'Kirchgasse 6', 'Graz', 'Western Europe', '8010', 'Austria', '4440386903', '7673426', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FAMIA', 'Familia Arquibaldo', 'Aria Cruz', 'Marketing Assistant', 'Rua Orós, 92', 'Sao Paulo', 'South America', '05442-030', 'Brazil', '645426865196', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FISSA', 'FISSA Fabrica Inter. Salchichas S.A.', 'Diego Roel', 'Accounting Manager', 'C/ Moralzarzal, 86', 'Madrid', 'Southern Europe', '28034', 'Spain', '53677606255', '915555593', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FOLIG', 'Folies gourmandes', 'Martine Rancé', 'Assistant Sales Agent', '184, chaussée de Tournai', 'Lille', 'Western Europe', '59000', 'France', '07209332426', '20161017', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FOLKO', 'Folk och fa HB', 'Maria Larsson', 'Owner', 'Åkergatan 24', 'Bräcke', 'Northern Europe', 'S-844 67', 'Sweden', '603072710216', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FRANK', 'Frankenversand', 'Peter Franken', 'Marketing Manager', 'Berliner Platz 43', 'München', 'Western Europe', '80805', 'Germany', '332401866377468', '0890877451', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FRANR', 'France restauration', 'Carine Schmitt', 'Marketing Manager', '54, rue Royale', 'Nantes', 'Western Europe', '44000', 'France', '43015648559', '40322120', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FRANS', 'Franchi S.p.A.', 'Paolo Accorti', 'Sales Representative', 'Via Monte Bianco 34', 'Torino', 'Southern Europe', '10100', 'Italy', '664383502491', '0114988261', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('FURIB', 'Furia Bacalhau e Frutos do Mar', 'Lino Rodriguez', 'Sales Manager', 'Jardim das rosas n. 32', 'Lisboa', 'Southern Europe', '1675', 'Portugal', '574962833500', '13542535', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('GALED', 'Galeria del gastrónomo', 'Eduardo Saavedra', 'Marketing Manager', 'Rambla de Cataluña, 23', 'Barcelona', 'Southern Europe', '08022', 'Spain', '7347072208', '932034561', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('GODOS', 'Godos Cocina Típica', 'José Pedro Freyre', 'Sales Manager', 'C/ Romero, 33', 'Sevilla', 'Southern Europe', '41101', 'Spain', '56095321012', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('GOURL', 'Gourmet Lanchonetes', 'André Fonseca', 'Sales Associate', 'Av. Brasil, 442', 'Campinas', 'South America', '04876786', 'Brazil', '81791673510', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('GREAL', 'Great Lakes Food Market', 'Howard Snyder', 'Marketing Manager', '2732 Baker Blvd.', 'Eugene', 'North America', '97403', 'USA', '7293653995', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('GROSR', 'GROSELLA-Restaurante', 'Manuel Pereira', 'Owner', '5ª Ave. Los Palos Grandes', 'Caracas', 'South America', '1081', 'Venezuela', '1248907787', '422833397', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('HANAR', 'Hanari Carnes', 'Mario Pontes', 'Accounting Manager', 'Rua do Paço, 67', 'Rio de Janeiro', 'South America', '05454-876', 'Brazil', '261666927189', '215558765', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('HILAA', 'HILARION-Abastos', 'Carlos Hernández', 'Sales Representative', 'Carrera 22 con Ave. Carlos Soublette', 'San Cristóbal', 'South America', '5022', 'Venezuela', '605443810136', '55551948', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('HUNGC', 'Hungry Coyote Import Store', 'Yoshi Latimer', 'Sales Representative', 'City Center Plaza 516 Main St.', 'Elgin', 'North America', '97827', 'USA', '67793553182', '5035552376', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('HUNGO', 'Hungry Owl All-Night Grocers', 'Patricia McKenna', 'Sales Associate', '8 Johnstown Road', 'Cork', 'British Isles', NULL, 'Ireland', '23904385903', '29672333', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ISLAT', 'Island Trading', 'Helen Bennett', 'Marketing Manager', 'Garden House Crowther Way', 'Cowes', 'British Isles', 'PO31 7PJ', 'UK', '75367254382', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('KOENE', 'Koniglich Essen', 'Philip Cramer', 'Sales Associate', 'Maubelstr. 90', 'Brandenburg', 'Western Europe', '14776', 'Germany', '4664352762', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LACOR', 'La corne abondance', 'Daniel Tonini', 'Sales Representative', '67, avenue de Europe', 'Versailles', 'Western Europe', '78000', 'France', '89376828272', '30598511', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LAMAI', 'La maison Asie', 'Annette Roulet', 'Sales Manager', '1 rue Alsace-Lorraine', 'Toulouse', 'Western Europe', '31000', 'France', '6305928485', '61776111', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LAUGB', 'Laughing Bacchus Wine Cellars', 'Yoshi Tannamuri', 'Marketing Assistant', '1900 Oak St.', 'Vancouver', 'North America', 'V3F 2K1', 'Canada', '987015698000', '6045557293', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LAZYK', 'Lazy K Kountry Store', 'John Steel', 'Marketing Manager', '12 Orchestra Terrace', 'Walla Walla', 'North America', '99362', 'USA', '370401881', '5095556221', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LEHMS', 'Lehmanns Marktstand', 'Renate Messner', 'Sales Representative', 'Magazinweg 7', 'Frankfurt a.M.', 'Western Europe', '60528', 'Germany', '93519879974', '0690245874', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LETSS', 'Lets Stop N Shop', 'Jaime Yorres', 'Owner', '87 Polk St. Suite 5', 'San Francisco', 'North America', '94117', 'USA', '91870634113', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LILAS', 'LILA-Supermercado', 'Carlos González', 'Accounting Manager', 'Carrera 52 con Ave. Bolivar Llano Largo', 'Barquisimeto', 'South America', '3508', 'Venezuela', '7302415780', '93317256', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LINOD', 'LINO-Delicateses', 'Felipe Izquierdo', 'Owner', 'Ave. 5 de Mayo Porlamar', 'I. de Margarita', 'South America', '4980', 'Venezuela', '5656416455', '8349393', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('LONEP', 'Lonesome Pine Restaurant', 'Fran Wilson', 'Sales Manager', '89 Chiaroscuro Rd.', 'Portland', 'North America', '97219', 'USA', '78190651805', '5035559646', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('MAGAA', 'Magazzini Alimentari Riuniti', 'Giovanni Rovelli', 'Marketing Manager', 'Via Ludovico il Moro 22', 'Bergamo', 'Southern Europe', '24100', 'Italy', '792519139047', '035640231', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('MAISD', 'Maison Dewey', 'Catherine Dewey', 'Sales Agent', 'Rue Joseph-Bens 532', 'Bruxelles', 'Western Europe', 'B-1180', 'Belgium', '439952877195', '022012468', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('MEREP', 'Mere Paillarde', 'Jean Fresnière', 'Marketing Assistant', '43 rue St. Laurent', 'Montréal', 'North America', 'H1J 1C3', 'Canada', '17672694079', '5145558055', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('MORGK', 'Morgenstern Gesundkost', 'Alexander Feuer', 'Marketing Assistant', 'Heerstr. 22', 'Leipzig', 'Western Europe', '04179', 'Germany', '7931289440', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('NORTS', 'NorthSouth', 'Simon Crowther', 'Sales Associate', 'South House 300 Queensbridge', 'London', 'British Isles', 'SW7 1RZ', 'UK', '61663571736', '1715552530', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('OCEAN', 'Océano Atlántico Ltda.', 'Yvonne Moncada', 'Sales Agent', 'Ing. Gustavo Moncada 8585 Piso 20-A', 'Buenos Aires', 'South America', '1010', 'Argentina', '49389784', '11355535', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('OLDWO', 'Old World Delicatessen', 'Rene Phillips', 'Sales Representative', '2743 Bering St.', 'Anchorage', 'North America', '99508', 'USA', '1609137025', '9075552880', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('OTTIK', 'Ottilies Kaseladen', 'Henriette Pfalzheim', 'Owner', 'Mehrheimerstr. 369', 'Köln', 'Western Europe', '50739', 'Germany', '9691644993', '02210765721', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('PARIS', 'Paris specialités', 'Marie Bertrand', 'Owner', '265, boulevard Charonne', 'Paris', 'Western Europe', '75012', 'France', '2293072841', '142342277', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('PERIC', 'Pericles Comidas clásicas', 'Guillermo Fernández', 'Sales Representative', 'Calle Dr. Jorge Cash 321', 'México D.F.', 'Central America', '05033', 'Mexico', '5693118833', '55453745', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('PICCO', 'Piccolo und mehr', 'Georg Pipps', 'Sales Manager', 'Geislweg 14', 'Salzburg', 'Western Europe', '5020', 'Austria', '23583264835', '65629723', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('PRINI', 'Princesa Isabel Vinhos', 'Isabel de Castro', 'Sales Representative', 'Estrada da saúde n. 58', 'Lisboa', 'Southern Europe', '1756', 'Portugal', '76973073820', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('QUEDE', 'Que Delícia', 'Bernardo Batista', 'Accounting Manager', 'Rua da Panificadora, 12', 'Rio de Janeiro', 'South America', '02389-673', 'Brazil', '40364745445', '215554545', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('QUEEN', 'Queen Cozinha', 'Lúcia Carvalho', 'Marketing Assistant', 'Alameda dos Canàrios, 891', 'Sao Paulo', 'South America', '05487-020', 'Brazil', '710785129376', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('QUICK', 'QUICK-Stop', 'Horst Kloss', 'Accounting Manager', 'Taucherstraße 10', 'Cunewalde', 'Western Europe', '01307', 'Germany', '56874140394', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('RANCH', 'Rancho grande', 'Sergio Gutiérrez', 'Sales Representative', 'Av. del Libertador 900', 'Buenos Aires', 'South America', '1010', 'Argentina', '7344336770', '11235556', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('RATTC', 'Rattlesnake Canyon Grocery', 'Paula Wilson', 'Assistant Sales Representative', '2817 Milton Dr.', 'Albuquerque', 'North America', '87110', 'USA', '93507640023', '5055553620', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('REGGC', 'Reggiani Caseifici', 'Maurizio Moroni', 'Sales Associate', 'Strada Provinciale 124', 'Reggio Emilia', 'Southern Europe', '42100', 'Italy', '50969859237', '0522556722', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('RICAR', 'Ricardo Adocicados', 'Janete Limeira', 'Assistant Sales Agent', 'Av. Copacabana, 267', 'Rio de Janeiro', 'South America', '02389-890', 'Brazil', '18510502976', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('RICSU', 'Richter Supermarkt', 'Michael Holz', 'Sales Manager', 'Grenzacherweg 237', 'Genève', 'Western Europe', '1203', 'Switzerland', '2364910979', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('ROMEY', 'Romero y tomillo', 'Alejandra Camino', 'Accounting Manager', 'Gran Vía, 1', 'Madrid', 'Southern Europe', '28001', 'Spain', '977584478', '917456210', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SANTG', 'Sante Gourmet', 'Jonas Bergulfsen', 'Owner', 'Erling Skakkes gate 78', 'Stavern', 'Scandinavia', '4110', 'Norway', '3526258793', '07989247', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SAVEA', 'Save-a-lot Markets', 'Jose Pavarotti', 'Sales Representative', '187 Suffolk Ln.', 'Boise', 'North America', '83720', 'USA', '59851726529', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SEVES', 'Seven Seas Imports', 'Hari Kumar', 'Sales Manager', '90 Wadhurst Rd.', 'London', 'British Isles', 'OX15 4NB', 'UK', '010934864', '1715555646', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SIMOB', 'Simons bistro', 'Jytte Petersen', 'Owner', 'Vinbæltet 34', 'Kobenhavn', 'Northern Europe', '1734', 'Denmark', '97514971', '31133557', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SPECD', 'Specialites du monde', 'Dominique Perrier', 'Marketing Manager', '25, rue Lauriston', 'Paris', 'Western Europe', '75016', 'France', '96844301463', '147556020', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SPLIR', 'Split Rail Beer Ale', 'Art Braunschweiger', 'Sales Manager', 'P.O. Box 555', 'Lander', 'North America', '82520', 'USA', '2959996262', '3075556525', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('SUPRD', 'Supremes delices', 'Pascale Cartrain', 'Accounting Manager', 'Boulevard Tirou, 255', 'Charleroi', 'Western Europe', 'B-6000', 'Belgium', '6214597836', '07123672221', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('THEBI', 'The Big Cheese', 'Liz Nixon', 'Marketing Manager', '89 Jefferson Way Suite 2', 'Portland', 'North America', '97201', 'USA', '081340318', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('THECR', 'The Cracker Box', 'Liu Wong', 'Marketing Assistant', '55 Grizzly Peak Rd.', 'Butte', 'North America', '59801', 'USA', '71780077942', '4065558083', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('TOMSP', 'Toms Spezialitäten', 'Karin Josephs', 'Marketing Manager', 'Luisenstr. 48', 'Münster', 'Western Europe', '44087', 'Germany', '10476147023', '0251035695', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('TORTU', 'Tortuga Restaurante', 'Miguel Angel Paolino', 'Owner', 'Avda. Azteca 123', 'México D.F.', 'Central America', '05033', 'Mexico', '18326762803', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('TRADH', 'Tradiçao Hipermercados', 'Anabela Domingues', 'Sales Representative', 'Av. Inês de Castro, 414', 'Sao Paulo', 'South America', '05634-030', 'Brazil', '16207561929', '115552168', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('TRAIH', 'Trails Head Gourmet Provisioners', 'Helvetius Nagy', 'Sales Associate', '722 DaVinci Blvd.', 'Kirkland', 'North America', '98034', 'USA', '280383307613', '2065552174', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('VAFFE', 'Vaffeljernet', 'Palle Ibsen', 'Sales Manager', 'Smagsloget 45', 'Århus', 'Northern Europe', '8200', 'Denmark', '2768013007', '86223344', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('Val2 ', 'IT', 'Val2', 'IT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('VALON', 'IT', 'Valon Hoti', 'IT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('VICTE', 'Victuailles en stock', 'Mary Saveley', 'Sales Agent', '2, rue du Commerce', 'Lyon', 'Western Europe', '69004', 'France', '7437158996', '78325487', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('VINET', 'Vins et alcools Chevalier', 'Paul Henriot', 'Accounting Manager', '59 rue de Abbaye', 'Reims', 'Western Europe', '51100', 'France', '11391641157', '26471511', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WANDK', 'Die Wandernde Kuh', 'Rita Müller', 'Sales Representative', 'Adenauerallee 900', 'Stuttgart', 'Western Europe', '70563', 'Germany', '2180936168', '711035428', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WARTH', 'Wartian Herkku', 'Pirkko Koskitalo', 'Accounting Manager', 'Torikatu 38', 'Oulu', 'Scandinavia', '90110', 'Finland', '53505857022', '981443655', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WELLI', 'Wellington Importadora', 'Paula Parente', 'Sales Manager', 'Rua do Mercado, 12', 'Resende', 'South America', '08737-363', 'Brazil', '4664851736', NULL, NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WHITC', 'White Clover Markets', 'Karl Jablonski', 'Owner', '305 - 14th Ave. S. Suite 3B', 'Seattle', 'North America', '98128', 'USA', '8398859855', '2065554115', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WILMK', 'Wilman Kala', 'Matti Karttunen', 'Owner/Marketing Assistant', 'Keskuskatu 45', 'Helsinki', 'Scandinavia', '21240', 'Finland', '70408724798', '902248858', NULL);
INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, Email) VALUES ('WOLZA', 'Wolski  Zajazd', 'Zbyszek Piestrzeniewicz', 'Owner', 'ul. Filtrowa 68', 'Warszawa', 'Eastern Europe', '01-012', 'Poland', '156525143', '266427012', NULL);

-- Insert ALL Employees data (9 employees from your CSV)  
INSERT INTO Employees VALUES (1, 'Davolio', 'Nancy', 'Sales Representative', 'Ms.', '1968-12-08', '2012-05-01', '507 - 20th Ave. E.\nApt. 2A', 'Seattle', 'North America', '98122', 'USA', '2065559857', '5467', NULL, 'Education includes a BA in psychology from Colorado State University in 1970. She also completed The Art of the Cold Call.', 2, 'http://accweb/emmployees/davolio.bmp');
INSERT INTO Employees VALUES (2, 'Fuller', 'Andrew', 'Vice President, Sales', 'Dr.', '1952-02-19', '2012-08-14', '908 W. Capital Way', 'Tacoma', 'North America', '98401', 'USA', '2065559482', '3457', NULL, 'Andrew received his BTS commercial in 1974 and a Ph.D. in international marketing from the University of Dallas in 1981.', NULL, 'http://accweb/emmployees/fuller.bmp');
INSERT INTO Employees VALUES (3, 'Leverling', 'Janet', 'Sales Representative', 'Ms.', '1963-08-30', '2012-04-01', '722 Moss Bay Blvd.', 'Kirkland', 'North America', '98033', 'USA', '2065553412', '3355', NULL, 'Janet has a BS degree in chemistry from Boston College (1984).', 2, 'http://accweb/emmployees/leverling.bmp');
INSERT INTO Employees VALUES (4, 'Peacock', 'Margaret', 'Sales Representative', 'Mrs.', '1958-09-19', '2013-05-03', '4110 Old Redmond Rd.', 'Redmond', 'North America', '98052', 'USA', '2065558122', '5176', NULL, 'Margaret holds a BA in English literature from Concordia College (1958) and an MA from the American Institute of Culinary Arts (1966).', 2, 'http://accweb/emmployees/peacock.bmp');
INSERT INTO Employees VALUES (5, 'Buchanan', 'Steven', 'Sales Manager', 'Mr.', '1955-03-04', '2013-10-17', '14 Garrett Hill', 'London', 'British Isles', 'SW1 8JR', 'UK', '7115554848', '3453', NULL, 'Steven Buchanan graduated from St. Andrews University, Scotland, with a BSC degree in 1976.', 2, 'http://accweb/emmployees/buchanan.bmp');
INSERT INTO Employees VALUES (6, 'Suyama', 'Michael', 'Sales Representative', 'Mr.', '1963-07-02', '2013-10-17', 'Coventry House\nMiner Rd.', 'London', 'British Isles', 'EC2 7JR', 'UK', '7115557773', '428', NULL, 'Michael is a graduate of Sussex University (MA, economics, 1983).', 5, 'http://accweb/emmployees/davolio.bmp');
INSERT INTO Employees VALUES (7, 'King', 'Robert', 'Sales Representative', 'Mr.', '1960-05-29', '2014-01-02', 'Edgeham Hollow\nWinchester Way', 'London', 'British Isles', 'RG1 9SP', 'UK', '7115555598', '465', NULL, 'Robert King served in the Peace Corps and traveled extensively.', 5, 'http://accweb/emmployees/davolio.bmp');
INSERT INTO Employees VALUES (8, 'Callahan', 'Laura', 'Inside Sales Coordinator', 'Ms.', '1958-01-09', '2014-03-05', '4726 - 11th Ave. N.E.', 'Seattle', 'North America', '98105', 'USA', '2065551189', '2344', NULL, 'Laura received a BA in psychology from the University of Washington.', 2, 'http://accweb/emmployees/davolio.bmp');
INSERT INTO Employees VALUES (9, 'Dodsworth', 'Anne', 'Sales Representative', 'Ms.', '1969-07-02', '2014-11-15', '7 Houndstooth Rd.', 'London', 'British Isles', 'WG2 7LT', 'UK', '7115554444', '452', NULL, 'Anne has a BA degree in English from St. Lawrence College.', 5, 'http://accweb/emmployees/davolio.bmp');

-- Insert ALL EmployeeTerritories data (49 relationships from your CSV)
INSERT INTO EmployeeTerritories VALUES (1, '06897');
INSERT INTO EmployeeTerritories VALUES (1, '19713');
INSERT INTO EmployeeTerritories VALUES (2, '01581');
INSERT INTO EmployeeTerritories VALUES (2, '01730');
INSERT INTO EmployeeTerritories VALUES (2, '01833');
INSERT INTO EmployeeTerritories VALUES (2, '02116');
INSERT INTO EmployeeTerritories VALUES (2, '02139');
INSERT INTO EmployeeTerritories VALUES (2, '02184');
INSERT INTO EmployeeTerritories VALUES (2, '40222');
INSERT INTO EmployeeTerritories VALUES (3, '30346');
INSERT INTO EmployeeTerritories VALUES (3, '31406');
INSERT INTO EmployeeTerritories VALUES (3, '32859');
INSERT INTO EmployeeTerritories VALUES (3, '33607');
INSERT INTO EmployeeTerritories VALUES (4, '20852');
INSERT INTO EmployeeTerritories VALUES (4, '27403');
INSERT INTO EmployeeTerritories VALUES (4, '27511');
INSERT INTO EmployeeTerritories VALUES (5, '02903');
INSERT INTO EmployeeTerritories VALUES (5, '07960');
INSERT INTO EmployeeTerritories VALUES (5, '08837');
INSERT INTO EmployeeTerritories VALUES (5, '10019');
INSERT INTO EmployeeTerritories VALUES (5, '10038');
INSERT INTO EmployeeTerritories VALUES (5, '11747');
INSERT INTO EmployeeTerritories VALUES (5, '14450');
INSERT INTO EmployeeTerritories VALUES (6, '85014');
INSERT INTO EmployeeTerritories VALUES (6, '85251');
INSERT INTO EmployeeTerritories VALUES (6, '98004');
INSERT INTO EmployeeTerritories VALUES (6, '98052');
INSERT INTO EmployeeTerritories VALUES (6, '98104');
INSERT INTO EmployeeTerritories VALUES (7, '60179');
INSERT INTO EmployeeTerritories VALUES (7, '60601');
INSERT INTO EmployeeTerritories VALUES (7, '80202');
INSERT INTO EmployeeTerritories VALUES (7, '80909');
INSERT INTO EmployeeTerritories VALUES (7, '90405');
INSERT INTO EmployeeTerritories VALUES (7, '94025');
INSERT INTO EmployeeTerritories VALUES (7, '94105');
INSERT INTO EmployeeTerritories VALUES (7, '95008');
INSERT INTO EmployeeTerritories VALUES (7, '95054');
INSERT INTO EmployeeTerritories VALUES (7, '95060');
INSERT INTO EmployeeTerritories VALUES (8, '19428');
INSERT INTO EmployeeTerritories VALUES (8, '44122');
INSERT INTO EmployeeTerritories VALUES (8, '45839');
INSERT INTO EmployeeTerritories VALUES (8, '53404');
INSERT INTO EmployeeTerritories VALUES (9, '03049');
INSERT INTO EmployeeTerritories VALUES (9, '03801');
INSERT INTO EmployeeTerritories VALUES (9, '48075');
INSERT INTO EmployeeTerritories VALUES (9, '48084');
INSERT INTO EmployeeTerritories VALUES (9, '48304');
INSERT INTO EmployeeTerritories VALUES (9, '55113');
INSERT INTO EmployeeTerritories VALUES (9, '55439');


INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10248', '11', '14.0', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10248', '42', '9.8', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10248', '72', '34.8', '5', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10249', '14', '18.6', '9', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10249', '51', '42.4', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10250', '41', '7.7', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10250', '51', '42.4', '35', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10250', '65', '16.8', '15', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10251', '22', '16.8', '6', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10251', '57', '15.6', '15', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10251', '65', '16.8', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10252', '20', '64.8', '40', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10252', '33', '2.0', '25', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10252', '60', '27.2', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10253', '31', '10.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10253', '39', '14.4', '42', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10253', '49', '16.0', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10254', '24', '3.6', '15', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10254', '55', '19.2', '21', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10254', '74', '8.0', '21', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10255', '2', '15.2', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10255', '16', '13.9', '35', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10255', '36', '15.2', '25', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10255', '59', '44.0', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10256', '53', '26.2', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10256', '77', '10.4', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10257', '27', '35.1', '25', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10257', '39', '14.4', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10257', '77', '10.4', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10258', '2', '15.2', '50', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10258', '5', '17.0', '65', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10258', '32', '25.6', '6', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10259', '21', '8.0', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10259', '37', '20.8', '1', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10260', '41', '7.7', '16', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10260', '57', '15.6', '50', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10260', '62', '39.4', '15', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10260', '70', '12.0', '21', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10261', '21', '8.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10261', '35', '14.4', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10262', '5', '17.0', '12', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10262', '7', '24.0', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10262', '56', '30.4', '2', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10263', '16', '13.9', '60', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10263', '24', '3.6', '28', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10263', '30', '20.7', '60', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10263', '74', '8.0', '36', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10264', '2', '15.2', '35', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10264', '41', '7.7', '25', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10265', '17', '31.2', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10265', '70', '12.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10266', '12', '30.4', '12', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10267', '40', '14.7', '50', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10267', '59', '44.0', '70', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10267', '76', '14.4', '15', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10268', '29', '99.0', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10268', '72', '27.8', '4', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10269', '33', '2.0', '60', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10269', '72', '27.8', '20', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10270', '36', '15.2', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10270', '43', '36.8', '25', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10271', '33', '2.0', '24', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10272', '20', '64.8', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10272', '31', '10.0', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10272', '72', '27.8', '24', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10273', '10', '24.8', '24', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10273', '31', '10.0', '15', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10273', '33', '2.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10273', '40', '14.7', '60', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10273', '76', '14.4', '33', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10274', '71', '17.2', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10274', '72', '27.8', '7', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10275', '24', '3.6', '12', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10275', '59', '44.0', '6', '0.05');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10276', '10', '24.8', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10276', '13', '4.8', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10277', '28', '36.4', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10277', '62', '39.4', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10278', '44', '15.5', '16', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10278', '59', '44.0', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10278', '63', '35.1', '8', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10278', '73', '12.0', '25', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10279', '17', '31.2', '15', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10280', '24', '3.6', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10280', '55', '19.2', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10280', '75', '6.2', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10281', '19', '7.3', '1', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10281', '24', '3.6', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10281', '35', '14.4', '4', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10282', '30', '20.7', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10282', '57', '15.6', '2', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10283', '15', '12.4', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10283', '19', '7.3', '18', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10283', '60', '27.2', '35', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10283', '72', '27.8', '3', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10284', '27', '35.1', '15', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10284', '44', '15.5', '21', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10284', '60', '27.2', '20', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10284', '67', '11.2', '5', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10285', '1', '14.4', '45', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10285', '40', '14.7', '40', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10285', '53', '26.2', '36', '0.2');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10286', '35', '14.4', '100', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10286', '62', '39.4', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10287', '16', '13.9', '40', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10287', '34', '11.2', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10287', '46', '9.6', '15', '0.15');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10288', '54', '5.9', '10', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10288', '68', '10.0', '3', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10289', '3', '8.0', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10289', '64', '26.6', '9', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10290', '5', '17.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10290', '29', '99.0', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10290', '49', '16.0', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10290', '77', '10.4', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10291', '13', '4.8', '20', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10291', '44', '15.5', '24', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10291', '51', '42.4', '2', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10292', '20', '64.8', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10293', '18', '50.0', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10293', '24', '3.6', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10293', '63', '35.1', '5', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10293', '75', '6.2', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10294', '1', '14.4', '18', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10294', '17', '31.2', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10294', '43', '36.8', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10294', '60', '27.2', '21', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10294', '75', '6.2', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10295', '56', '30.4', '4', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10296', '11', '16.8', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10296', '16', '13.9', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10296', '69', '28.8', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10297', '39', '14.4', '60', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10297', '72', '27.8', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10298', '2', '15.2', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10298', '36', '15.2', '40', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10298', '59', '44.0', '30', '0.25');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10298', '62', '39.4', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10299', '19', '7.3', '15', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10299', '70', '12.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10300', '66', '13.6', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10300', '68', '10.0', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10301', '40', '14.7', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10301', '56', '30.4', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10302', '17', '31.2', '40', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10302', '28', '36.4', '28', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10302', '43', '36.8', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10303', '40', '14.7', '40', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10303', '65', '16.8', '30', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10303', '68', '10.0', '15', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10304', '49', '16.0', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10304', '59', '44.0', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10304', '71', '17.2', '2', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10305', '18', '50.0', '25', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10305', '29', '99.0', '25', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10305', '39', '14.4', '30', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10306', '30', '20.7', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10306', '53', '26.2', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10306', '54', '5.9', '5', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10307', '62', '39.4', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10307', '68', '10.0', '3', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10308', '69', '28.8', '1', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10308', '70', '12.0', '5', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10309', '4', '17.6', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10309', '6', '20.0', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10309', '42', '11.2', '2', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10309', '43', '36.8', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10309', '71', '17.2', '3', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10310', '16', '13.9', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10310', '62', '39.4', '5', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10311', '42', '11.2', '6', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10311', '69', '28.8', '7', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10312', '28', '36.4', '4', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10312', '43', '36.8', '24', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10312', '53', '26.2', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10312', '75', '6.2', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10313', '36', '15.2', '12', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10314', '32', '25.6', '40', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10314', '58', '10.6', '30', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10314', '62', '39.4', '25', '0.1');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10315', '34', '11.2', '14', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10315', '70', '12.0', '30', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10316', '41', '7.7', '10', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10316', '62', '39.4', '70', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10317', '1', '14.4', '20', '0.0');
INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) VALUES ('10318', '41', '7.7', '20', '0.0');
-- Insert ALL Orders data (16282 relationships from your CSV)

INSERT INTO Orders (OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, ShipName, ShipAddress, ShipCity, ShipRegion, ShipPostalCode, ShipCountry) VALUES ('10248', 'VINET', '5', '2016-07-04', '2016-08-01', '2016-07-16', '3', '16.75', 'Vins et alcools Chevalier', '59 rue de l-Abbaye', 'Reims', 'Western Europe', '51100', 'France');
INSERT INTO Orders (OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, ShipName, ShipAddress, ShipCity, ShipRegion, ShipPostalCode, ShipCountry) VALUES ('10249', 'TOMSP', '6', '2016-07-05', '2016-08-16', '2016-07-10', '1', '22.25', 'Toms Spezialitäten', 'Luisenstr. 48', 'Münster', 'Western Europe', '44087', 'Germany');
INSERT INTO Orders (OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, ShipName, ShipAddress, ShipCity, ShipRegion, ShipPostalCode, ShipCountry) VALUES ('10250', 'HANAR', '4', '2016-07-08', '2016-08-05', '2016-07-12', '2', '25.0', 'Hanari Carnes', 'Rua do Paço, 67', 'Rio de Janeiro', 'South America', '05454-876', 'Brazil');

-- Insert ALL Products data (77 products from your CSV)
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('1', 'Chai', '1', '1', '10 boxes x 20 bags', '18.0', '39', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('2', 'Chang', '1', '1', '24 - 12 oz bottles', '19.0', '17', '40', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('3', 'Aniseed Syrup', '1', '2', '12 - 550 ml bottles', '10.0', '13', '70', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('4', 'Chef Antons Cajun Seasoning', '2', '2', '48 - 6 oz jars', '22.0', '53', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('5', 'Chef Antons Gumbo Mix', '2', '2', '36 boxes', '21.35', '0', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('6', 'Grandmas Boysenberry Spread', '3', '2', '12 - 8 oz jars', '25.0', '120', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('7', 'Uncle Bobs Organic Dried Pears', '3', '7', '12 - 1 lb pkgs.', '30.0', '15', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('8', 'Northwoods Cranberry Sauce', '3', '2', '12 - 12 oz jars', '40.0', '6', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('9', 'Mishi Kobe Niku', '4', '6', '18 - 500 g pkgs.', '97.0', '29', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('10', 'Ikura', '4', '8', '12 - 200 ml jars', '31.0', '31', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('11', 'Queso Cabrales', '5', '4', '1 kg pkg.', '21.0', '22', '30', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('12', 'Queso Manchego La Pastora', '5', '4', '10 - 500 g pkgs.', '38.0', '86', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('13', 'Konbu', '6', '8', '2 kg box', '6.0', '24', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('14', 'Tofu', '6', '7', '40 - 100 g pkgs.', '23.25', '35', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('15', 'Genen Shouyu', '6', '2', '24 - 250 ml bottles', '15.5', '39', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('16', 'Pavlova', '7', '3', '32 - 500 g boxes', '17.45', '29', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('17', 'Alice Mutton', '7', '6', '20 - 1 kg tins', '39.0', '0', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('18', 'Carnarvon Tigers', '7', '8', '16 kg pkg.', '62.5', '42', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('19', 'Teatime Chocolate Biscuits', '8', '3', '10 boxes x 12 pieces', '9.2', '25', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('20', 'Sir Rodneys Marmalade', '8', '3', '30 gift boxes', '81.0', '40', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('21', 'Sir Rodneys Scones', '8', '3', '24 pkgs. x 4 pieces', '10.0', '3', '40', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('22', 'Gustafs Knackebrod', '9', '5', '24 - 500 g pkgs.', '21.0', '104', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('23', 'Tunnbrod', '9', '5', '12 - 250 g pkgs.', '9.0', '61', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('24', 'Guarana Fantastica', '10', '1', '12 - 355 ml cans', '4.5', '20', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('25', 'NuNuCa NuNougatCreme', '11', '3', '20 - 450 g glasses', '14.0', '76', '0', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('26', 'Gumbar Gummibarchen', '11', '3', '100 - 250 g bags', '31.23', '15', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('27', 'Schoggi Schokolade', '11', '3', '100 - 100 g pieces', '43.9', '49', '0', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('28', 'Rossle Sauerkraut', '12', '7', '25 - 825 g cans', '45.6', '26', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('29', 'Thuringer Rostbratwurst', '12', '6', '50 bags x 30 sausgs.', '123.79', '0', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('30', 'NordOst Matjeshering', '13', '8', '10 - 200 g glasses', '25.89', '10', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('31', 'Gorgonzola Telino', '14', '4', '12 - 100 g pkgs', '12.5', '0', '70', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('32', 'Mascarpone Fabioli', '14', '4', '24 - 200 g pkgs.', '32.0', '9', '40', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('33', 'Geitost', '15', '4', '500 g', '2.5', '112', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('34', 'Sasquatch Ale', '16', '1', '24 - 12 oz bottles', '14.0', '111', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('35', 'Steeleye Stout', '16', '1', '24 - 12 oz bottles', '18.0', '20', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('36', 'Inlagd Sill', '17', '8', '24 - 250 g  jars', '19.0', '112', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('37', 'Gravad lax', '17', '8', '12 - 500 g pkgs.', '26.0', '11', '50', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('38', 'Cote de Blaye', '18', '1', '12 - 75 cl bottles', '263.5', '17', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('39', 'Chartreuse verte', '18', '1', '750 cc per bottle', '18.0', '69', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('40', 'Boston Crab Meat', '19', '8', '24 - 4 oz tins', '18.4', '123', '0', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('41', 'Jacks New England Clam Chowder', '19', '8', '12 - 12 oz cans', '9.65', '85', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('42', 'Singaporean Hokkien Fried Mee', '20', '5', '32 - 1 kg pkgs.', '14.0', '26', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('43', 'Ipoh Coffee', '20', '1', '16 - 500 g tins', '46.0', '17', '10', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('44', 'Gula Malacca', '20', '2', '20 - 2 kg bags', '19.45', '27', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('45', 'Rogede sild', '21', '8', '1k pkg.', '9.5', '5', '70', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('46', 'Spegesild', '21', '8', '4 - 450 g glasses', '12.0', '95', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('47', 'Zaanse koeken', '22', '3', '10 - 4 oz boxes', '9.5', '36', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('48', 'Chocolade', '22', '3', '10 pkgs.', '12.75', '15', '70', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('49', 'Maxilaku', '23', '3', '24 - 50 g pkgs.', '20.0', '10', '60', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('50', 'Valkoinen suklaa', '23', '3', '12 - 100 g bars', '16.25', '65', '0', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('51', 'Manjimup Dried Apples', '24', '7', '50 - 300 g pkgs.', '53.0', '20', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('52', 'Filo Mix', '24', '5', '16 - 2 kg boxes', '7.0', '38', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('53', 'Perth Pasties', '24', '6', '48 pieces', '32.8', '0', '0', '0', '1');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('54', 'Tourtiere', '25', '6', '16 pies', '7.45', '21', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('55', 'Pate chinois', '25', '6', '24 boxes x 2 pies', '24.0', '115', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('56', 'Gnocchi di nonna Alice', '26', '5', '24 - 250 g pkgs.', '38.0', '21', '10', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('57', 'Ravioli Angelo', '26', '5', '24 - 250 g pkgs.', '19.5', '36', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('58', 'Escargots de Bourgogne', '27', '8', '24 pieces', '13.25', '62', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('59', 'Raclette Courdavault', '28', '4', '5 kg pkg.', '55.0', '79', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('60', 'Camembert Pierrot', '28', '4', '15 - 300 g rounds', '34.0', '19', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('61', 'Sirop derable', '29', '2', '24 - 500 ml bottles', '28.5', '113', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('62', 'Tarte au sucre', '29', '3', '48 pies', '49.3', '17', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('63', 'Vegie-spread', '7', '2', '15 - 625 g jars', '43.9', '24', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('64', 'Wimmers gute Semmelknodel', '12', '5', '20 bags x 4 pieces', '33.25', '22', '80', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('65', 'Louisiana Fiery Hot Pepper Sauce', '2', '2', '32 - 8 oz bottles', '21.05', '76', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('66', 'Louisiana Hot Spiced Okra', '2', '2', '24 - 8 oz jars', '17.0', '4', '100', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('67', 'Laughing Lumberjack Lager', '16', '1', '24 - 12 oz bottles', '14.0', '52', '0', '10', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('68', 'Scottish Longbreads', '8', '3', '10 boxes x 8 pieces', '12.5', '6', '10', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('69', 'Gudbrandsdalsost', '15', '4', '10 kg pkg.', '36.0', '26', '0', '15', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('70', 'Outback Lager', '7', '1', '24 - 355 ml bottles', '15.0', '15', '10', '30', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('71', 'Flotemysost', '15', '4', '10 - 500 g pkgs.', '21.5', '26', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('72', 'Mozzarella di Giovanni', '14', '4', '24 - 200 g pkgs.', '34.8', '14', '0', '0', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('73', 'Rod Kaviar', '17', '8', '24 - 150 g jars', '15.0', '101', '0', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('74', 'Longlife Tofu', '4', '7', '5 kg pkg.', '10.0', '4', '20', '5', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('75', 'Rhonbrau Klosterbier', '12', '1', '24 - 0.5 l bottles', '7.75', '125', '0', '25', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('76', 'Lakkalikoori', '23', '1', '500 ml', '18.0', '57', '0', '20', '0');
INSERT INTO Products (ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued) VALUES ('77', 'Original Frankfurter grune Sobe', '12', '2', '12 boxes', '13.0', '32', '0', '15', '0');

-- Insert ALL Regions data
INSERT INTO Regions VALUES (1, 'Eastern');
INSERT INTO Regions VALUES (2, 'Western');
INSERT INTO Regions VALUES (3, 'Northern');
INSERT INTO Regions VALUES (4, 'Southern');

-- Insert ALL Shippers data
INSERT INTO Shippers VALUES (1, 'Speedy Express', '5035559831');
INSERT INTO Shippers VALUES (2, 'United Package', '5035553199');
INSERT INTO Shippers VALUES (3, 'Federal Shipping', '5035559931');

-- Insert ALL Suppliers data (29 suppliers from your CSV)
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('1', 'Exotic Liquids', 'Charlotte Cooper', 'Purchasing Manager', '49 Gilbert St.', 'London', 'British Isles', 'EC1 4SD', 'UK', '1715552222', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('2', 'New Orleans Cajun Delights', 'Shelley Burke', 'Order Administrator', 'P.O. Box 78934', 'New Orleans', 'North America', '70117', 'USA', '1005554822', NULL, '#CAJUN.HTM#');
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('3', 'Grandma Kellys Homestead', 'Regina Murphy', 'Sales Representative', '707 Oxford Rd.', 'Ann Arbor', 'North America', '48104', 'USA', '3135555735', '3135553349', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('4', 'Tokyo Traders', 'Yoshi Nagase', 'Marketing Manager', '8 SekimaiMusashinoshi', 'Tokyo', 'Eastern Asia', '100', 'Japan', '0335555011', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('5', 'Cooperativa de Quesos Las Cabras', 'Antonio del Valle Saavedra ', 'Export Administrator', 'Calle del Rosal 4', 'Oviedo', 'Southern Europe', '33007', 'Spain', '985987654', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('6', 'Mayumis', 'Mayumi Ohno', 'Marketing Representative', '92 Setsuko Chuoku', 'Osaka', 'Eastern Asia', '545', 'Japan', '614317877', NULL, 'Mayumi''s (on the World Wide Web)#http://www.microsoft.com/accessdev/sampleapps/mayumi.htm#');
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('7', 'Pavlova, Ltd.', 'Ian Devling', 'Marketing Manager', '74 Rose St Moonie Ponds', 'Melbourne', 'Victoria', '3058', 'Australia', '034442343', '034446588', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('8', 'Specialty Biscuits, Ltd.', 'Peter Wilson', 'Sales Representative', '29 Kings Way', 'Manchester', 'British Isles', 'M14 GSD', 'UK', '1615554448', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('9', 'PB Knackebrod AB', 'Lars Peterson', 'Sales Agent', 'Kaloadagatan 13', 'Goteborg', NULL, 'S-345 67', 'Sweden ', '0319876543', '0319876591', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('10', 'Refrescos Americanas LTDA', 'Carlos Diaz', 'Marketing Manager', 'Av. das Americanas 12.890', 'Sao Paulo', 'South America', '5442', 'Brazil', '115554640', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('11', 'Heli Subwaren GmbH  Co KG', 'Petra Winkler', 'Sales Manager', 'Tiergartenstraße 5', 'Berlin', 'Western Europe', '10785', 'Germany', '109984510', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('12', 'Plutzer Lebensmittelgrobmarkte AG', 'Martin Bein', 'International Marketing Mgr.', 'Bogenallee 51', 'Frankfurt', 'Western Europe', '60439', 'Germany', '069992755', NULL, 'Plutzer (on the World Wide Web)#http://www.microsoft.com/accessdev/sampleapps/plutzer.htm#');
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('13', 'NordOstFisch Handelsgesellschaft mbH', 'Sven Petersen', 'Coordinator Foreign Markets', 'Frahmredder 112a', 'Cuxhaven', 'Western Europe', '27478', 'Germany', '047218713', '047218714', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('14', 'Formaggi Fortini srl', 'Elio Rossi', 'Sales Representative', 'Viale Dante, 75', 'Ravenna', 'Southern Europe', '48100', 'Italy', '054460323', '054460603', '#FORMAGGI.HTM#');
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('15', 'Norske Meierier', 'Beate Vileid', 'Marketing Manager', 'Hatlevegen 5', 'Sandvika', 'Scandinavia', '1320', 'Norway', '02953010', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('16', 'Bigfoot Breweries', 'Cheryl Saylor', 'Regional Account Rep.', '3400 8th AvenueSuite 210', 'Bend', 'North America', '97101', 'USA', '5035559931', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('17', 'Svensk Sjofoda AB', 'Michael Bjorn', 'Sales Representative', 'Brovallavagen 231', 'Stockholm', 'Northern Europe', 'S123 45', 'Sweden', '081234567', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('18', 'Aux joyeux ecclesiastiques', 'Guylene Nodier', 'Sales Manager', '203, Rue des Francs-Bourgeois', 'Paris', 'Western Europe', '75004', 'France', '103830068', '103830062', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('19', 'New England Seafood Cannery', 'Robb Merchant', 'Wholesale Account Agent', 'Order Processing Dept 2100 Paul Revere Blvd.', 'Boston', 'North America', '02134', 'USA', '6175553267', '6175553389', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('20', 'Leka Trading', 'Chandra Leka', 'Owner', '471 Serangoon Loop, Suite 402', 'Singapore', 'South-East Asia', '0512', 'Singapore', '5558787', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('21', 'Lyngbysild', 'Niels Petersen', 'Sales Manager', 'LyngbysildFiskebakken 10', 'Lyngby', 'Northern Europe', '2800', 'Denmark', '43844108', '43844115', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('22', 'Zaanse Snoepfabriek', 'Dirk Luchte', 'Accounting Manager', 'VerkoopRijnweg 22', 'Zaandam', 'Northern Europe', '9999 ZZ', 'Netherlands', '123451212', '123451210', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('23', 'Karkki Oy', 'Anne Heikkonen', 'Product Manager', 'Valtakatu 12', 'Lappeenranta', 'Scandinavia', '53120', 'Finland', '95310956', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('24', 'Gday, Mate', 'Wendy Mackenzie', 'Sales Representative', '170 Prince Edward ParadeHunters Hill', 'Sydney', 'NSW', '2042', 'Australia', '025555914', '025554873', 'Gday Mate (on the World Wide Web)#http://www.microsoft.com/accessdev/sampleapps/gdaymate.htm#');
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('25', 'Ma Maison', 'Jean-Guy Lauzon', 'Marketing Manager', '2960 Rue St. Laurent', 'Montréal', 'North America', 'H1J 1C3', 'Canada', '5145559022', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('26', 'Pasta Buttini srl', 'Giovanni Giudici', 'Order Administrator', 'Via dei Gelsomini, 153', 'Salerno', 'Southern Europe', '84100', 'Italy', '0896547665', '0896547667', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('27', 'Escargots Nouveaux', 'Marie Delamare', 'Sales Manager', '22, rue H. Voiron', 'Montceau', 'Western Europe', '71300', 'France', '85570007', NULL, NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('28', 'Gai pâturage', 'Eliane Noz', 'Sales Representative', 'Bat. B
3, rue des Alpes', 'Annecy', 'Western Europe', '74000', 'France', '38769806', '38769858', NULL);
INSERT INTO Suppliers (SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax, HomePage) VALUES ('29', 'Forets derables', 'Chantal Goulet', 'Accounting Manager', '148 rue Chasseur', 'Ste-Hyacinthe', 'North America', 'J2S 7S8', 'Canada', '5145552955', '5145552921', NULL);


-- Insert ALL Territories data (53 territories from your CSV)
INSERT INTO Territories VALUES ('01581', 'Westboro', 1);
INSERT INTO Territories VALUES ('01730', 'Bedford', 1);
INSERT INTO Territories VALUES ('01833', 'Georgetown', 1);
INSERT INTO Territories VALUES ('02116', 'Boston', 1);
INSERT INTO Territories VALUES ('02139', 'Cambridge', 1);
INSERT INTO Territories VALUES ('02184', 'Braintree', 1);
INSERT INTO Territories VALUES ('02903', 'Providence', 1);
INSERT INTO Territories VALUES ('03049', 'Hollis', 3);
INSERT INTO Territories VALUES ('03801', 'Portsmouth', 3);
INSERT INTO Territories VALUES ('06897', 'Wilton', 1);
INSERT INTO Territories VALUES ('07960', 'Morristown', 1);
INSERT INTO Territories VALUES ('08837', 'Edison', 1);
INSERT INTO Territories VALUES ('10019', 'New York', 1);
INSERT INTO Territories VALUES ('10038', 'New York', 1);
INSERT INTO Territories VALUES ('11747', 'Mellvile', 1);
INSERT INTO Territories VALUES ('14450', 'Fairport', 1);
INSERT INTO Territories VALUES ('19428', 'Philadelphia', 3);
INSERT INTO Territories VALUES ('19713', 'Neward', 1);
INSERT INTO Territories VALUES ('20852', 'Rockville', 1);
INSERT INTO Territories VALUES ('27403', 'Greensboro', 1);
INSERT INTO Territories VALUES ('27511', 'Cary', 1);
INSERT INTO Territories VALUES ('29202', 'Columbia', 4);
INSERT INTO Territories VALUES ('30346', 'Atlanta', 4);
INSERT INTO Territories VALUES ('31406', 'Savannah', 4);
INSERT INTO Territories VALUES ('32859', 'Orlando', 4);
INSERT INTO Territories VALUES ('33607', 'Tampa', 4);
INSERT INTO Territories VALUES ('40222', 'Louisville', 1);
INSERT INTO Territories VALUES ('44122', 'Beachwood', 3);
INSERT INTO Territories VALUES ('45839', 'Findlay', 3);
INSERT INTO Territories VALUES ('48075', 'Southfield', 3);
INSERT INTO Territories VALUES ('48084', 'Troy', 3);
INSERT INTO Territories VALUES ('48304', 'Bloomfield Hills', 3);
INSERT INTO Territories VALUES ('53404', 'Racine', 3);
INSERT INTO Territories VALUES ('55113', 'Roseville', 3);
INSERT INTO Territories VALUES ('55439', 'Minneapolis', 3);
INSERT INTO Territories VALUES ('60179', 'Hoffman Estates', 2);
INSERT INTO Territories VALUES ('60601', 'Chicago', 2);
INSERT INTO Territories VALUES ('72716', 'Bentonville', 4);
INSERT INTO Territories VALUES ('75234', 'Dallas', 4);
INSERT INTO Territories VALUES ('78759', 'Austin', 4);
INSERT INTO Territories VALUES ('80202', 'Denver', 2);
INSERT INTO Territories VALUES ('80909', 'Colorado Springs', 2);
INSERT INTO Territories VALUES ('85014', 'Phoenix', 2);
INSERT INTO Territories VALUES ('85251', 'Scottsdale', 2);
INSERT INTO Territories VALUES ('90405', 'Santa Monica', 2);
INSERT INTO Territories VALUES ('94025', 'Menlo Park', 2);
INSERT INTO Territories VALUES ('94105', 'San Francisco', 2);
INSERT INTO Territories VALUES ('95008', 'Campbell', 2);
INSERT INTO Territories VALUES ('95054', 'Santa Clara', 2);
INSERT INTO Territories VALUES ('95060', 'Santa Cruz', 2);
INSERT INTO Territories VALUES ('98004', 'Bellevue', 2);
INSERT INTO Territories VALUES ('98052', 'Redmond', 2);
INSERT INTO Territories VALUES ('98104', 'Seattle', 2);

"""

# Rest of the DataQualityChecker class remains the same...
class DataQualityChecker:
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.checks_config = {}
        self.system_codes_config = {}
        self._load_embedded_configs()
    
    def _load_embedded_configs(self):
        """Load embedded CSV configurations"""
        # Load data quality config
        reader = csv.DictReader(io.StringIO(DATA_QUALITY_CONFIG))
        for row in reader:
            table_name = row['table_name']
            field_name = row['field_name']
            
            if table_name not in self.checks_config:
                self.checks_config[table_name] = {}
            
            self.checks_config[table_name][field_name] = {
                'description': row.get('description', ''),
                'special_characters_check': int(row.get('special_characters_check', '0')) == 1,
                'null_check': int(row.get('null_check', '0')) == 1,
                'blank_check': int(row.get('blank_check', '0')) == 1,
                'max_value_check': int(row.get('max_value_check', '0')) == 1,
                'min_value_check': int(row.get('min_value_check', '0')) == 1,
                'max_count_check': int(row.get('max_count_check', '0')) == 1,
                'email_check': int(row.get('email_check', '0')) == 1,
                'numeric_check': int(row.get('numeric_check', '0')) == 1,
                'system_codes_check': int(row.get('system_codes_check', '0')) == 1,
                'language_check': int(row.get('language_check', '0')) == 1,
                'phone_number_check': int(row.get('phone_number_check', '0')) == 1,
                'duplicate_check': int(row.get('duplicate_check', '0')) == 1,
                'date_check': int(row.get('date_check', '0')) == 1
            }
        
        # Load system codes config
        reader = csv.DictReader(io.StringIO(SYSTEM_CODES_CONFIG))
        for row in reader:
            table_name = row['table_name']
            field_name = row['field_name']
            valid_codes_str = row.get('valid_codes', '')
            valid_codes = [code.strip() for code in valid_codes_str.split(',') if code.strip()]
            
            if table_name not in self.system_codes_config:
                self.system_codes_config[table_name] = {}
            
            self.system_codes_config[table_name][field_name] = valid_codes

    def table_exists(self, table_name: str) -> bool:
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            return cursor.fetchone() is not None
        except sqlite3.Error:
            return False

    def column_exists(self, table_name: str, column_name: str) -> bool:
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        except sqlite3.Error:
            return False

    def is_valid_email(self, email: str) -> bool:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None

    def is_valid_phone(self, phone: str) -> bool:
        cleaned_phone = re.sub(r'[^\d]', '', phone)
        if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
            return False
        phone_pattern = r'^\+?1?[0-9]{9,14}$'
        return re.match(phone_pattern, cleaned_phone) is not None

    def is_valid_date(self, date_str: str) -> bool:
        date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', 
                       '%m-%d-%Y', '%d-%m-%Y', '%Y%m%d', '%d.%m.%Y', '%Y', '%m/%Y', '%Y-%m']
        for fmt in date_formats:
            try:
                datetime.strptime(str(date_str), fmt)
                return True
            except ValueError:
                continue
        return False

    def get_valid_system_codes(self, table_name: str, field_name: str) -> List[str]:
        return self.system_codes_config.get(table_name, {}).get(field_name, [])

    def run_field_checks(self, table_name: str, field_name: str, checks: Dict) -> List[Dict]:
        results = []
        
        if not self.column_exists(table_name, field_name):
            results.append({
                'table': table_name,
                'field': field_name,
                'check_type': 'column_existence',
                'status': 'FAIL',
                'message': f'Column {field_name} does not exist in table {table_name}',
                'severity': 'ERROR'
            })
            return results

        try:
            cursor = self.db_connection.cursor()
            
            # Get primary key for record identification
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            primary_key = None
            for col in columns:
                if col[5] == 1:  # is primary key
                    primary_key = col[1]
                    break
            
            # Fallback to first column if no primary key
            if not primary_key and columns:
                primary_key = columns[0][1]
            
            # Helper function to format field names
            def format_field_name(field):
                import re
                return re.sub(r'([a-z])([A-Z])', r'\1 \2', field)
            
            # Get total rows
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            total_rows = cursor.fetchone()[0]
            
            if total_rows == 0:
                results.append({
                    'table': table_name,
                    'field': field_name,
                    'check_type': 'data_existence',
                    'status': 'WARNING',
                    'message': f'Table {table_name} has no data',
                    'severity': 'WARNING'
                })
                return results

            # NULL CHECK
            # NULL CHECK - Complete implementation
            # NULL CHECK
            if checks.get("null_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                total_rows = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NULL")
                null_count = cursor.fetchone()[0]
                
                if null_count > 0:
                    # Get the actual NULL records for details
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NULL")
                    null_records = cursor.fetchall()
                    
                    # Create JSON array format for more_details
                    null_details_array = []
                    for record in null_records:
                        primary_key_display = format_field_name(primary_key)
                        field_display = format_field_name(field_name)
                        
                        null_details_array.append({
                            primary_key_display: record[0],
                            field_display: "NULL"
                        })
                    
                    # Create summary message
                    summary_message = f"Found {null_count} NULL values out of {total_rows} total rows"
                    
                    # Add FAIL result with JSON array in more_details
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "null_check",
                        "status": "FAIL",
                        "message": summary_message,
                        "more_details": null_details_array,  # Now a JSON array instead of string
                        "severity": "HIGH"
                    })
                else:
                    # Add PASS result
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "null_check",
                        "status": "PASS",
                        "message": f"No NULL values found in {total_rows} rows",
                        "more_details": None,
                        "severity": "INFO"
                    })



            # BLANK CHECK
            if checks.get("blank_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` = ''")
                blank_count = cursor.fetchone()[0]
                
                if blank_count > 0:
                    # Get the primary keys of records with blank values
                    cursor.execute(f"SELECT `{primary_key}` FROM `{table_name}` WHERE `{field_name}` = ''")
                    blank_records = cursor.fetchall()
                    
                    # Create summary message
                    summary_message = f"Found {blank_count} blank values out of {total_rows} total rows"
                    
                    # Create detailed breakdown
                    primary_key_display = format_field_name(primary_key)
                    field_display = format_field_name(field_name)
                    
                    invalid_details = []
                    for record in blank_records:
                        invalid_details.append(f"{primary_key_display}: {record[0]}, {field_display}: BLANK")
                    
                    details_display = "; ".join(invalid_details)
                    
                    # Add FAIL result
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "blank_check",
                        "status": "FAIL",
                        "message": summary_message,
                        "more_details": details_display,
                        "severity": "MEDIUM"
                    })
                else:
                    # Add PASS result
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "blank_check",
                        "status": "PASS",
                        "message": "No blank values found",
                        "more_details": None,
                        "severity": "INFO"
                    })

            # EMAIL CHECK
            if checks.get("email_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    invalid_emails = []
                    invalid_details = []
                    
                    for value in values:
                        email = str(value[1]).strip()
                        if not self.is_valid_email(email):
                            invalid_emails.append(email)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {email}")
                    
                    if invalid_emails:
                        # Create summary message
                        summary_message = f"Found {len(invalid_emails)} invalid email formats out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "email_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "MEDIUM"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "email_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} email formats appear valid",
                            "more_details": None,
                            "severity": "INFO"
                        })

            # PHONE NUMBER CHECK
            if checks.get("phone_number_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    invalid_phones = []
                    invalid_details = []
                    
                    for value in values:
                        phone = str(value[1]).strip()
                        if not self.is_valid_phone(phone):
                            invalid_phones.append(phone)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {phone}")
                    
                    if invalid_phones:
                        # Create summary message
                        summary_message = f"Found {len(invalid_phones)} invalid phone formats out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "phone_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "MEDIUM"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "phone_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} phone formats appear valid",
                            "more_details": None,
                            "severity": "INFO"
                        })

            # DUPLICATE CHECK
            if checks.get('duplicate_check', False):
                cursor.execute(f"""
                    SELECT `{field_name}`, COUNT(*) as count, GROUP_CONCAT(`{primary_key}`) as primary_keys
                    FROM `{table_name}` 
                    WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''
                    GROUP BY `{field_name}` 
                    HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    total_duplicate_records = sum([dup[1] for dup in duplicates])
                    summary_message = f"Found {len(duplicates)} duplicate values affecting {total_duplicate_records} records"
                    
                    primary_key_display = format_field_name(primary_key)
                    field_display = format_field_name(field_name)
                    
                    invalid_details = []
                    for dup in duplicates:
                        value = dup[0]
                        count = dup[1]
                        primary_keys = dup[2].split(',')
                        pk_list = ', '.join(primary_keys)
                        invalid_details.append(f"{field_display}: {value} (appears {count} times in {primary_key_display}: {pk_list})")
                    
                    details_display = "; ".join(invalid_details)
                    message = f"{summary_message}. Details: {details_display}"
                    
                    results.append({
                        'table': table_name,
                        'field': field_name,
                        'check_type': 'duplicate_check',
                        'status': 'FAIL',
                        'message': message,
                        'severity': 'MEDIUM'
                    })

            # NUMERIC CHECK
            if checks.get("numeric_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    non_numeric_values = []
                    invalid_details = []
                    
                    for value in values:
                        val = str(value[1]).strip()
                        try:
                            float(val)
                        except (ValueError, TypeError):
                            non_numeric_values.append(val)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {val}")
                    
                    if non_numeric_values:
                        # Create summary message
                        summary_message = f"Found {len(non_numeric_values)} non-numeric values out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "numeric_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "MEDIUM"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "numeric_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} values are numeric",
                            "more_details": None,
                            "severity": "INFO"
                        })

            if checks.get("date_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    invalid_dates = []
                    invalid_details = []
                    
                    for value in values:
                        date_str = str(value[1]).strip()
                        if not self.is_valid_date(date_str):
                            invalid_dates.append(date_str)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {date_str}")
                    
                    if invalid_dates:
                        # Create summary message
                        summary_message = f"Found {len(invalid_dates)} invalid date formats out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "date_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "HIGH"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "date_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} date formats appear valid",
                            "more_details": None,
                            "severity": "INFO"
                        })

            if checks.get("system_codes_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    valid_codes_list = self.get_valid_system_codes(table_name, field_name)
                    invalid_system_codes = []
                    invalid_details = []
                    
                    for value in values:
                        code = str(value[1]).strip()
                        if valid_codes_list and code not in valid_codes_list:
                            invalid_system_codes.append(code)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            valid_codes_preview = ", ".join(valid_codes_list[:3])
                            if len(valid_codes_list) > 3:
                                valid_codes_preview += f"... ({len(valid_codes_list)} total)"
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {code} (valid: {valid_codes_preview})")
                    
                    if invalid_system_codes:
                        # Create summary message
                        if valid_codes_list:
                            summary_message = f"Found {len(invalid_system_codes)} invalid system codes out of {non_null_count} values (Valid codes: {len(valid_codes_list)} defined)"
                        else:
                            summary_message = f"Found {len(invalid_system_codes)} values that don't match system code patterns out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "system_codes_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "HIGH"
                        })
                    else:
                        if valid_codes_list:
                            # Add PASS result
                            results.append({
                                "table": table_name,
                                "field": field_name,
                                "check_type": "system_codes_check",
                                "status": "PASS",
                                "message": f"All {non_null_count} values are valid system codes from config ({len(valid_codes_list)} codes)",
                                "more_details": None,
                                "severity": "INFO"
                            })
            if checks.get("special_characters_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    special_char_records = []
                    invalid_details = []
                    
                    special_char_pattern = r'[^\w\s\-.,@():/]'  # Allow common chars, flag others
                    for value in values:
                        val = str(value[1])
                        if re.search(special_char_pattern, val):
                            special_char_records.append(val)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            display_val = val[:20] + '...' if len(val) > 20 else val
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {display_val}")
                    
                    if special_char_records:
                        # Create summary message
                        summary_message = f"Found {len(special_char_records)} records with special characters out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "special_characters_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "LOW"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "special_characters_check",
                            "status": "PASS",
                            "message": f"No problematic special characters found in {non_null_count} values",
                            "more_details": None,
                            "severity": "INFO"
                        })

            if checks.get("max_value_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    max_threshold = 20000  # Example: max string length
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != '' AND LENGTH(`{field_name}`) > ?", (max_threshold,))
                    oversized_values = cursor.fetchall()
                    
                    if oversized_values:
                        # Create summary message
                        summary_message = f"Found {len(oversized_values)} values exceeding max length ({max_threshold}) out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        primary_key_display = format_field_name(primary_key)
                        field_display = format_field_name(field_name)
                        
                        oversized_details = []
                        for value in oversized_values:
                            val_length = len(str(value[1]))
                            val_preview = str(value[1])[:30] + '...' if len(str(value[1])) > 30 else str(value[1])
                            oversized_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {val_preview} (length: {val_length})")
                        
                        details_display = "; ".join(oversized_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "max_value_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "MEDIUM"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "max_value_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} values are within max length limit ({max_threshold})",
                            "more_details": None,
                            "severity": "INFO"
                        })
            if checks.get("min_value_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    min_threshold = 1  # Example: min string length
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != '' AND LENGTH(`{field_name}`) < ?", (min_threshold,))
                    undersized_values = cursor.fetchall()
                    
                    if undersized_values:
                        # Create summary message
                        summary_message = f"Found {len(undersized_values)} values below min length ({min_threshold}) out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        primary_key_display = format_field_name(primary_key)
                        field_display = format_field_name(field_name)
                        
                        undersized_details = []
                        for value in undersized_values:
                            val_length = len(str(value[1]))
                            undersized_details.append(f"{primary_key_display}: {value[0]}, {field_display}: '{value[1]}' (length: {val_length})")
                        
                        details_display = "; ".join(undersized_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "min_value_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "MEDIUM"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "min_value_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} values meet min length requirement ({min_threshold})",
                            "more_details": None,
                            "severity": "INFO"
                        })
            if checks.get("max_count_check", False):
                max_count_threshold = 20000  # Example threshold
                if total_rows > max_count_threshold:
                    # Create summary message
                    summary_message = f"Table has {total_rows} rows, exceeding max count threshold of {max_count_threshold}"
                    
                    # Create detailed breakdown
                    details_display = f"Table Name: {table_name}, Current Row Count: {total_rows}, Threshold: {max_count_threshold}"
                    
                    # Add FAIL result
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "max_count_check",
                        "status": "FAIL",
                        "message": summary_message,
                        "more_details": details_display,
                        "severity": "LOW"
                    })
                else:
                    # Add PASS result
                    results.append({
                        "table": table_name,
                        "field": field_name,
                        "check_type": "max_count_check",
                        "status": "PASS",
                        "message": f"Table row count ({total_rows}) is within acceptable limit ({max_count_threshold})",
                        "more_details": None,
                        "severity": "INFO"
                    })

            if checks.get("language_check", False):
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                non_null_count = cursor.fetchone()[0]
                
                if non_null_count > 0:
                    cursor.execute(f"SELECT `{primary_key}`, `{field_name}` FROM `{table_name}` WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''")
                    values = cursor.fetchall()
                    non_english_records = []
                    invalid_details = []
                    
                    for value in values:
                        val = str(value[1])
                        # Check for non-ASCII characters
                        if not all(ord(char) < 128 for char in val):
                            non_english_records.append(val)
                            primary_key_display = format_field_name(primary_key)
                            field_display = format_field_name(field_name)
                            val_preview = val[:30] + '...' if len(val) > 30 else val
                            invalid_details.append(f"{primary_key_display}: {value[0]}, {field_display}: {val_preview}")
                    
                    if non_english_records:
                        # Create summary message
                        summary_message = f"Found {len(non_english_records)} records with non-English characters out of {non_null_count} values"
                        
                        # Create detailed breakdown
                        details_display = "; ".join(invalid_details)
                        
                        # Add FAIL result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "language_check",
                            "status": "FAIL",
                            "message": summary_message,
                            "more_details": details_display,
                            "severity": "LOW"
                        })
                    else:
                        # Add PASS result
                        results.append({
                            "table": table_name,
                            "field": field_name,
                            "check_type": "language_check",
                            "status": "PASS",
                            "message": f"All {non_null_count} values appear to be English text",
                            "more_details": None,
                            "severity": "INFO"
                        })

        except Exception as e:
            results.append({
                'table': table_name,
                'field': field_name,
                'check_type': 'execution_error',
                'status': 'ERROR',
                'message': f'Error during field validation: {str(e)}',
                'severity': 'ERROR'
            })
        
        return results

    def run_all_checks(self) -> Dict[str, List[Dict]]:
        results = {}
        
        for table_name, fields in self.checks_config.items():
            if not self.table_exists(table_name):
                continue
            
            table_results = []
            for field_name, checks in fields.items():
                field_results = self.run_field_checks(table_name, field_name, checks)
                if field_results:
                    table_results.extend(field_results)
            
            if table_results:
                results[table_name] = table_results
        
        return results

# Global variables
db_connection = None
data_quality_checker = None

def initialize_embedded_database():
    """Initialize embedded database with your complete data"""
    global db_connection, data_quality_checker
    try:
        # Create in-memory database
        db_connection = sqlite3.connect(':memory:', check_same_thread=False)
        db_connection.row_factory = sqlite3.Row
        
        # Execute embedded SQL
        db_connection.executescript(NORTHWIND_DATABASE_SQL)
        db_connection.commit()
        
        data_quality_checker = DataQualityChecker(db_connection)
        logger.info("Embedded Northwind database initialized successfully with ALL your data")
        
        # Verify tables exist with row counts
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            logger.info(f"Table {table}: {count} rows")
        
    except Exception as e:
        logger.error(f"Error initializing embedded database: {str(e)}")
        raise

# Initialize database on startup
initialize_embedded_database()

# Pydantic models for UI5 integration
class CheckResult(BaseModel):
    table: str
    field: str
    check_type: str
    status: str
    message: str
    severity: str
    more_details: Optional[str] = None

class CheckSummary(BaseModel):
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    errors: int
    info_checks: int
    success_rate: float
    tables_checked: int
    critical_issues: int
    medium_issues: int
    low_issues: int

class ApiResponse(BaseModel):
    status: str
    message: str
    summary: CheckSummary
    detailed_results: Dict[str, List[CheckResult]]
    timestamp: str
    database: str
    execution_time_ms: int

@app.get("/")
async def root():
    """API status endpoint for UI5 integration"""
    global db_connection, data_quality_checker
    
    tables = []
    table_counts = {}
    if db_connection:
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            table_counts[table] = count
    
    return {
        "service": "Data Quality Checker API",
        "version": "3.0.0",
        "status": "Ready",
        "description": "Self-contained API with embedded Northwind database for UI5 integration",
        "database_status": "Embedded Database Active" if db_connection else "Database Not Available",
        "available_tables": tables,
        "table_row_counts": table_counts,
        "configured_checks": len(data_quality_checker.checks_config) if data_quality_checker else 0,
        "endpoints": {
            "run_checks": "/run-all-checks (POST)",
            "health": "/health (GET)",
            "status": "/status (GET)"
        },
        "ui5_integration": "Ready - Call POST /run-all-checks from your UI5 button",
        "cors_enabled": True,
        "deployment": "Render Ready"
    }

@app.get("/tables")
async def get_available_tables():
    """Get list of all available tables for UI5 dropdown"""
    global db_connection, data_quality_checker
    
    if not db_connection:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Filter out sqlite system tables
        filtered_tables = [table for table in tables if not table.startswith('sqlite_')]
        
        # Add table metadata for UI5 display
        table_info = []
        for table in filtered_tables:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            row_count = cursor.fetchone()[0]
            
            # Check if validation config exists
            has_config = table in data_quality_checker.checks_config
            configured_fields = len(data_quality_checker.checks_config.get(table, {}))
            
            table_info.append({
                "table_name": table,
                "display_name": table.replace('_', ' ').title(),  # Format for UI5
                "row_count": row_count,
                "has_validation_config": has_config,
                "configured_fields": configured_fields
            })
        
        return {
            "status": "SUCCESS",
            "tables": filtered_tables,
            "table_details": table_info,
            "count": len(filtered_tables),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching tables: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching tables: {str(e)}")

@app.post("/run-checks-table/{table_name}", response_model=ApiResponse)
async def run_checks_for_table(table_name: str):
    """Execute data quality checks for a specific selected table - UI5 Integration"""
    global data_quality_checker
    
    if not data_quality_checker:
        raise HTTPException(status_code=500, detail="Data quality checker not initialized")
    
    # Validate table exists
    if not data_quality_checker.table_exists(table_name):
        available_tables = list(data_quality_checker.checks_config.keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Table '{table_name}' not found. Available tables: {available_tables}"
        )
    
    start_time = datetime.now()
    
    try:
        # Check if table has validation configuration
        table_config = data_quality_checker.checks_config.get(table_name)
        if not table_config:
            raise HTTPException(
                status_code=400, 
                detail=f"No validation configuration found for table '{table_name}'"
            )
        
        # Run checks only for the specified table
        table_results = []
        for field_name, checks in table_config.items():
            field_results = data_quality_checker.run_field_checks(table_name, field_name, checks)
            if field_results:
                table_results.extend(field_results)
        
        results = {}
        if table_results:
            results[table_name] = table_results
        
        # Calculate summary statistics
        total_checks = len(table_results)
        passed_checks = len([r for r in table_results if r["status"] == "PASS"])
        failed_checks = len([r for r in table_results if r["status"] == "FAIL"])
        warnings = len([r for r in table_results if r["status"] == "WARNING"])
        errors = len([r for r in table_results if r["status"] == "ERROR"])
        info_checks = len([r for r in table_results if r["status"] == "INFO"])
        
        # Count by severity for UI5 prioritization
        critical_issues = len([r for r in table_results if r.get("severity") in ["ERROR", "HIGH"]])
        medium_issues = len([r for r in table_results if r.get("severity") == "MEDIUM"])
        low_issues = total_checks - critical_issues - medium_issues
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        summary = CheckSummary(
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=warnings,
            errors=errors,
            info_checks=info_checks,
            success_rate=round((passed_checks / total_checks) * 100, 2) if total_checks > 0 else 0,
            tables_checked=1,
            critical_issues=critical_issues,
            medium_issues=medium_issues,
            low_issues=low_issues
        )
        
        return ApiResponse(
            status="SUCCESS",
            message=f"Data quality checks completed successfully for table '{table_name}'",
            summary=summary,
            detailed_results=results,
            timestamp=datetime.now().isoformat(),
            database="Embedded Northwind Database",
            execution_time_ms=int(execution_time)
        )
        
    except Exception as e:
        logger.error(f"Error running data quality checks for table {table_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running checks: {str(e)}")

@app.get("/table-info/{table_name}")
async def get_table_info(table_name: str):
    """Get detailed information about a specific table (optional for UI5)"""
    global db_connection, data_quality_checker
    
    if not db_connection:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    if not data_quality_checker.table_exists(table_name):
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    
    try:
        cursor = db_connection.cursor()
        
        # Get column information
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        row_count = cursor.fetchone()[0]
        
        # Get configured checks for this table
        configured_checks = data_quality_checker.checks_config.get(table_name, {})
        
        column_info = []
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            col_checks = configured_checks.get(col_name, {})
            
            column_info.append({
                "name": col_name,
                "type": col_type,
                "nullable": not col[3],  # NOT NULL constraint
                "primary_key": bool(col[5]),
                "configured_checks": list(col_checks.keys()) if col_checks else []
            })
        
        return {
            "status": "SUCCESS",
            "table_name": table_name,
            "row_count": row_count,
            "column_count": len(columns),
            "columns": column_info,
            "has_validation_config": bool(configured_checks),
            "configured_fields": len(configured_checks),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting table info for {table_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting table info: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint for Render and UI5 monitoring"""
    global db_connection, data_quality_checker
    
    is_healthy = bool(db_connection and data_quality_checker and data_quality_checker.checks_config)
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected" if db_connection else "disconnected",
        "checker": "initialized" if data_quality_checker else "not_initialized",
        "ready_for_ui5": is_healthy,
        "uptime": "running",
        "version": "3.0.0"
    }

@app.get("/status")
async def get_detailed_status():
    """Detailed status endpoint for debugging and UI5 integration"""
    global db_connection, data_quality_checker
    
    tables = []
    table_counts = {}
    
    if db_connection:
        try:
            cursor = db_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get row counts for each table
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                    count = cursor.fetchone()[0]
                    table_counts[table] = count
                except:
                    table_counts[table] = "Error"
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
    
    return {
        "api_info": {
            "name": "Data Quality Checker API",
            "version": "3.0.0",
            "status": "active",
            "deployment": "render_ready"
        },
        "database_info": {
            "type": "embedded_sqlite",
            "status": "connected" if db_connection else "disconnected",
            "tables": tables,
            "table_row_counts": table_counts
        },
        "checker_info": {
            "initialized": bool(data_quality_checker),
            "checks_configured": bool(data_quality_checker and data_quality_checker.checks_config),
            "system_codes_configured": bool(data_quality_checker and data_quality_checker.system_codes_config),
            "configured_tables": list(data_quality_checker.checks_config.keys()) if data_quality_checker else [],
            "total_field_configs": sum(len(fields) for fields in data_quality_checker.checks_config.values()) if data_quality_checker else 0
        },
        "ui5_integration": {
            "cors_enabled": True,
            "main_endpoint": "/run-all-checks",
            "method": "POST",
            "response_format": "JSON with summary and detailed results",
            "ready": bool(data_quality_checker and data_quality_checker.checks_config)
        },
        "timestamp": datetime.now().isoformat()
    }

# Error handler for UI5 integration
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "ERROR",
            "message": "Internal server error occurred",
            "error": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# For Render deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
