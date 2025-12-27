


$fn=180;

difference() {
cube([118.2,4,38.2]);

translate([2,2,2])
    cube([114.2,4,34.2]);
    
    translate([80,5,20])
    rotate([90,0,0])
        cylinder(10,5,5);

}

