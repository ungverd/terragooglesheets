# terragooglesheets
Gets BOM from googledocs and gets necessary components links, pn and price from terrraelectronica and onelec

To use this script you must have json five called lscomponents.json for auth (read google docs api to get it)

Give sheet id and number of rows as a parameter (for example terragoogle.py sheet_id 15 45 will get all components for 15-45 rows).
you may use only sheet id, in this case while BOM would be processed

Boom is to have following headers: value, reference, footprint, type, quantity, price, pn, url in any order. Other headers are ignored. Footprint sholdbe specified as "Resistor_0603" (part after _ is taken)
Use Type column to specify parts type ("capacitor", "resistor", "inductor" for parametrical search in terra) and "pn" for search by 
part of partnumber. Script will fill price, pn and url columns and create columns for comments and description

Example of correct BOM beginning
Reference	Type	Quantity	Value	Footprint  //headers
C22	Capacitor	4	18pF	Capacitors:CAP_0603  //search for capacitor 18pF 0603  (used dielectris np0, x5r, x7r, y7v ignored)
DA3,	PN	1	NCP511SN25	SOT:SOT23-5        //search for pn started with NCP511SN25
L11,	Inductor	1	10nH	Inductors:IND_0402 //search for Inductor 0402 case 10nH
R1,	Resistor	1	1M	Resistors:RES_0603     //search for 1M Resistor 0603 1% tolerance
