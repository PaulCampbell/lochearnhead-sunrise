



// main box
difference() {
cube([114,35,34]);
translate([2,2,2])
cube([110,37,30]); 
}

//corners
module corner_pillar() {
    difference() {
        cube([4,35,4]);
        translate([2,36,2])
        rotate([90,0,0])
            cylinder(3,0.5,0.5, $fn=80);
    }
}
corner_pillar();

translate([0,0,30])
    corner_pillar();

translate([110,0,30])
    corner_pillar();

translate([110,0,0])
    corner_pillar();



// battery mounts
translate([4,2,2])
    cube([6,4,6]);

translate([4,2,26])
    cube([6,4,6]);

translate([99,2,2])
    cube([6,4,6]);

translate([99,2,26])
    cube([6,4,6]);


// strap brackets
translate([30,0,32])
    difference() {
        cube([50,5,10]);
        translate([5,-1,0])
            cube([40,11,5]);  
}

translate([30,0,-10])
    difference() {
        cube([50,5,12]);
        translate([5,-1,6])
            cube([40,11,5]);  
}