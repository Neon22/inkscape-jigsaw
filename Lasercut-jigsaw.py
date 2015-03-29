#! /usr/bin/env python
'''
Copyright (C) 2011 Mark Schafer <neon.mark (a) gmail dot com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

# Build a Jigsaw puzzle for Lasercutting.
# User defines:
# - dimensions,
# - number of pieces in X and Y,
# - notch size,
# - random amount of perturbation for uniqueness,
# - border and rounding for border and inner corners
# - random or random seed for repeats

### 0.1 make basic jigsaw for lasercut - March 2011
### 0.2 add random seed so repeatable, add pieces for manual booleans - May 2011

### Todo
# add option to cut pieces:
#    - taking two rows(cols) at a time - reverse the second one and concat on end - add z to close
#    - taking a row and a col - do intersect = piece.

__version__ = "0.2"

import inkex, simplestyle, simpletransform, cubicsuperpath
from simplepath import *
import sys, math, random, copy

def randomize((x, y), radius, norm=True, absolute=False):
    """ return x,y moved by a random amount inside a radius.
        use uniform distribution unless
         - norm = True - then use a normal distribution
        If absolute is true - ensure random is only added to x,y  """
    # if norm:
        # r = abs(random.normalvariate(0.0,0.5*radius))
    # else:
        # r = random.uniform(0.0,radius)
    a = random.uniform(0.0,2*math.pi)
    x += math.cos(a)*radius
    y += math.sin(a)*radius
    if absolute:
        x = abs(x)
        y = abs(y)
    return [x, y]


def add_rounded_rectangle(startx, starty, radius, width, height, style, name, parent, mask=False):
    line_path = [['M', [startx, starty+radius]]]
    if radius > 0.0: # rounded corners
        line_path.append(['c', [0, -radius/2, radius/2, -radius, radius, -radius]])
        if mask == "Below":
               line_path.append(['m', [width-2*radius, 0,]])
        else:
            line_path.append(['c', [radius/2, 0, width-2*radius-radius/2, 0, width-2*radius,0 ]]) # top line
        line_path.append(['c', [radius/2, 0, radius, radius/2, radius, radius]])
        line_path.append(['c', [0, radius/2, 0, height-2*radius-radius/2, 0, height-2*radius]]) # RHS line
        line_path.append(['c', [0, radius/2, -radius/2, radius, -radius, radius]])
        line_path.append(['c', [-radius/2,0, -width+2*radius+radius/2,0, -width+2*radius,0]]) # bottom line
        line_path.append(['c', [-radius/2, 0, -radius, -radius/2, -radius, -radius]])
        if mask == "Right":
            line_path.append(['m', [0, height]])
        else:
            line_path.append(['c', [0, -radius/2, 0, -height+2*radius+radius/2, 0, -height+2*radius]]) # LHS line
    else: # square corners
        if mask == "Below":
            line_path.append(['m', [width, 0]])
            line_path.append(['l', [0, height, -width, 0, 0, -height]])
        elif mask == "Right":
            line_path.append(['l', [width, 0, 0, height, -width, 0,]])
        else: # separate
            line_path.append(['l', [width, 0, 0, height, -width, 0, 0, -height]])
    #
    #sys.stderr.write("%s\n"% line_path)
    attribs = {'style':simplestyle.formatStyle(style),
                    inkex.addNS('label','inkscape'):name,
                    'd':formatPath(line_path)}
    #sys.stderr.write("%s\n"% attribs)
    inkex.etree.SubElement(parent, inkex.addNS('path','svg'), attribs )



###----------------------
### all for intersection  from http://www.kevlindev.com/gui/index.htm
"""polynomial constructor
    Polynomial.prototype.init = function(coefs) {
    this.coefs = new Array();

    for ( var i = coefs.length - 1; i >= 0; i-- )
        this.coefs.push( coefs[i] );

    this._variable = "t";
    this._s = 0;   """

def get_derivative(polynomial):
    """ Polynomial.prototype.getDerivative = function() {
    var derivative = new Polynomial();

    for ( var i = 1; i < this.coefs.length; i++ ) {
        derivative.coefs.push(i*this.coefs[i]);
    }

    return derivative;   """
    deriv = []
    for i in range(len(polynomial)):
        deriv.append(i* polynomial[i])
    return deriv


def getroots_in_interval():
    """ Polynomial.prototype.getRootsInInterval = function(min, max) {
    var roots = new Array();
    var root;

    if ( this.getDegree() == 1 ) {
        root = this.bisection(min, max);
        if ( root != null ) roots.push(root);
    } else {
        // get roots of derivative
        var deriv  = this.getDerivative();
        var droots = deriv.getRootsInInterval(min, max);

        if ( droots.length > 0 ) {
            // find root on [min, droots[0]]
            root = this.bisection(min, droots[0]);
            if ( root != null ) roots.push(root);

            // find root on [droots[i],droots[i+1]] for 0 <= i <= count-2
            for ( i = 0; i <= droots.length-2; i++ ) {
                root = this.bisection(droots[i], droots[i+1]);
                if ( root != null ) roots.push(root);
            }

            // find root on [droots[count-1],xmax]
            root = this.bisection(droots[droots.length-1], max);
            if ( root != null ) roots.push(root);
        } else {
            // polynomial is monotone on [min,max], has at most one root
            root = this.bisection(min, max);
            if ( root != null ) roots.push(root);
        }
    }

    return roots;   """
    pass


def bisection(polynomial, minimum, maximum):
    """ Polynomial.prototype.bisection = function(min, max) {
    var minValue = this.eval(min);
    var maxValue = this.eval(max);
    var result;
    
    if ( Math.abs(minValue) <= Polynomial.TOLERANCE )
        result = min;
    else if ( Math.abs(maxValue) <= Polynomial.TOLERANCE )
        result = max;
    else if ( minValue * maxValue <= 0 ) {
        var tmp1  = Math.log(max - min);
        var tmp2  = Math.LN10 * Polynomial.ACCURACY;
        var iters = Math.ceil( (tmp1+tmp2) / Math.LN2 );

        for ( var i = 0; i < iters; i++ ) {
            result = 0.5 * (min + max);
            var value = this.eval(result);

            if ( Math.abs(value) <= Polynomial.TOLERANCE ) {
                break;
            }

            if ( value * minValue < 0 ) {
                max = result;
                maxValue = value;
            } else {
                min = result;
                minValue = value;
            }
        }
    }

    return result;   """
    pass


##def intersect_bezier(a1, a2, a3, a4, b1, b2, b3, b4):
##    """
##        """
##    # Calculate the coefficients of cubic polynomial
##    #a = a1.multiply(-1);
##    a = [i*-1 for i in a1]
##    #b = a2.multiply(3);
##    b = [i*3 for i in a2]
##    #c = a3.multiply(-3);
##    c = [i*-3 for i in a3]
##    #d = a.add(b.add(c.add(a4)));
##    d = [a[i]+b[i]+c[i]+a4[i] for i in range(len(a))]
##    #c13 = new Vector2D(d.x, d.y);
##    c13 = copy.deepcopy(d)
##
##    #a = a1.multiply(3);
##    a = [i*3 for i in a1]
##    #b = a2.multiply(-6);
##    b = [i*-6 for i in a2]
##    #c = a3.multiply(3);
##    c = [i*3 for i in a3]
##    #d = a.add(b.add(c));
##    d = [a[i]+b[i]+c[i] for i in range(len(a))]
##    #c12 = new Vector2D(d.x, d.y);
##    c12 = copy.deepcopy(d)
##
##    #a = a1.multiply(-3);
##    a = [i*-3 for i in a1]
##    #b = a2.multiply(3);
##    b = [i*3 for i in a2]
##    #c = a.add(b);
##    c = [a[i]+b[i] for i in range(len(a))]
##    #c11 = new Vector2D(c.x, c.y);
##    c11 = copy.deepcopy(c)
##    #c10 = new Vector2D(a1.x, a1.y);
##    c10 = copy.deepcopy(a1)
##
##    #a = b1.multiply(-1);
##    a = [i*-1 for i in b1]
##    #b = b2.multiply(3);
##    b = [i*3 for i in b2]
##    #c = b3.multiply(-3);
##    c = [i*-3 for i in b3]
##    #d = a.add(b.add(c.add(b4)));
##    d = [a[i]+b[i]+c[i]+b4[i] for i in range(len(a))]
##    #c23 = new Vector2D(d.x, d.y);
##    c23 = copy.deepcopy(d)
##
##    #a = b1.multiply(3);
##    a = [i*3 for i in b1]
##    #b = b2.multiply(-6);
##    b = [i*-6 for i in b2]
##    #c = b3.multiply(3);
##    c = [i*3 for i in b3]
##    #d = a.add(b.add(c));
##    d = [b[i]+c[i] for i in range(len(b))]
##    #c22 = new Vector2D(d.x, d.y);
##    c22 = copy.deepcopy(d)
##
##    #a = b1.multiply(-3);
##    a = [i*-3 for i in b1]
##    #b = b2.multiply(3);
##    b = [i*3 for i in b2]
##    #c = a.add(b);
##    c = [a[i]+b[i] for i in range(len(a))]
##    #c21 = new Vector2D(c.x, c.y);
##    c21 = copy.deepcopy(c)
##    #c20 = new Vector2D(b1.x, b1.y);
##    c20 = copy.deepcopy(b)
##
##    c10x2 = c10[0]*c10[0]
##    c10x3 = c10[0]*c10[0]*c10[0]
##    c10y2 = c10[1]*c10[1]
##    c10y3 = c10.y*c10[1]*c10[1]
##    c11x2 = c11[0]*c11[0]
##    c11x3 = c11[0]*c11[0]*c11[0]
##    c11y2 = c11[1]*c11[1]
##    c11y3 = c11[1]*c11[1]*c11[1]
##    c12x2 = c12[0]*c12[0]
##    c12x3 = c12[0]*c12[0]*c12[0]
##    c12y2 = c12[1]*c12.[1]
##    c12y3 = c12[1]*c12[1]*c12[1]
##    c13x2 = c13[0]*c13[0]
##    c13x3 = c13[0]*c13[0]*c13[0]
##    c13y2 = c13[1]*c13[1]
##    c13y3 = c13[1]*c13[1]*c13[1]
##    c20x2 = c20[0]*c20[0]
##    c20x3 = c20[0]*c20[0]*c20[0]
##    c20y2 = c20[1]*c20[1]
##    c20y3 = c20[1]*c20[1]*c20[1]
##    c21x2 = c21[0]*c21[0]
##    c21x3 = c21[0]*c21[0]*c21[0]
##    c21y2 = c21[1]*c21[1]
##    c22x2 = c22[0]*c22[0]
##    c22x3 = c22[0]*c22[0]*c22[0]
##    c22y2 = c22[1]*c22[1]
##    c23x2 = c23[0]*c23[0]
##    c23x3 = c23[0]*c23[0]*c23[0]
##    c23y2 = c23[1]*c23[1]
##    c23y3 = c23[1]*c23[1]*c23[1]
##    # create degree 9 (10 coef) polynomial
##    poly = [-c13x3*c23y3 + c13y3*c23x3 - 3*c13.x*c13y2*c23x2*c23.y + 3*c13x2*c13.y*c23.x*c23y2,
##            -6*c13.x*c22.x*c13y2*c23.x*c23.y + 6*c13x2*c13.y*c22.y*c23.x*c23.y + 3*c22.x*c13y3*c23x2 -
##                3*c13x3*c22.y*c23y2 - 3*c13.x*c13y2*c22.y*c23x2 + 3*c13x2*c22.x*c13.y*c23y2,
##            -6*c21.x*c13.x*c13y2*c23.x*c23.y - 6*c13.x*c22.x*c13y2*c22.y*c23.x + 6*c13x2*c22.x*c13.y*c22.y*c23.y +
##                3*c21.x*c13y3*c23x2 + 3*c22x2*c13y3*c23.x + 3*c21.x*c13x2*c13.y*c23y2 - 3*c13.x*c21.y*c13y2*c23x2 -
##                3*c13.x*c22x2*c13y2*c23.y + c13x2*c13.y*c23.x*(6*c21.y*c23.y + 3*c22y2) + c13x3*(-c21.y*c23y2 -
##                2*c22y2*c23.y - c23.y*(2*c21.y*c23.y + c22y2)),
##            c11.x*c12.y*c13.x*c13.y*c23.x*c23.y - c11.y*c12.x*c13.x*c13.y*c23.x*c23.y + 6*c21.x*c22.x*c13y3*c23.x +
##                3*c11.x*c12.x*c13.x*c13.y*c23y2 + 6*c10.x*c13.x*c13y2*c23.x*c23.y - 3*c11.x*c12.x*c13y2*c23.x*c23.y -
##                3*c11.y*c12.y*c13.x*c13.y*c23x2 - 6*c10.y*c13x2*c13.y*c23.x*c23.y - 6*c20.x*c13.x*c13y2*c23.x*c23.y +
##                3*c11.y*c12.y*c13x2*c23.x*c23.y - 2*c12.x*c12y2*c13.x*c23.x*c23.y - 6*c21.x*c13.x*c22.x*c13y2*c23.y -
##                6*c21.x*c13.x*c13y2*c22.y*c23.x - 6*c13.x*c21.y*c22.x*c13y2*c23.x + 6*c21.x*c13x2*c13.y*c22.y*c23.y +
##                2*c12x2*c12.y*c13.y*c23.x*c23.y + c22x3*c13y3 - 3*c10.x*c13y3*c23x2 + 3*c10.y*c13x3*c23y2 +
##                3*c20.x*c13y3*c23x2 + c12y3*c13.x*c23x2 - c12x3*c13.y*c23y2 - 3*c10.x*c13x2*c13.y*c23y2 +
##                3*c10.y*c13.x*c13y2*c23x2 - 2*c11.x*c12.y*c13x2*c23y2 + c11.x*c12.y*c13y2*c23x2 - c11.y*c12.x*c13x2*c23y2 +
##                2*c11.y*c12.x*c13y2*c23x2 + 3*c20.x*c13x2*c13.y*c23y2 - c12.x*c12y2*c13.y*c23x2 -
##                3*c20.y*c13.x*c13y2*c23x2 + c12x2*c12.y*c13.x*c23y2 - 3*c13.x*c22x2*c13y2*c22.y +
##                c13x2*c13.y*c23.x*(6*c20.y*c23.y + 6*c21.y*c22.y) + c13x2*c22.x*c13.y*(6*c21.y*c23.y + 3*c22y2) +
##                c13x3*(-2*c21.y*c22.y*c23.y - c20.y*c23y2 - c22.y*(2*c21.y*c23.y + c22y2) - c23.y*(2*c20.y*c23.y + 2*c21.y*c22.y)),
##            6*c11.x*c12.x*c13.x*c13.y*c22.y*c23.y + c11.x*c12.y*c13.x*c22.x*c13.y*c23.y + c11.x*c12.y*c13.x*c13.y*c22.y*c23.x -
##                c11.y*c12.x*c13.x*c22.x*c13.y*c23.y - c11.y*c12.x*c13.x*c13.y*c22.y*c23.x - 6*c11.y*c12.y*c13.x*c22.x*c13.y*c23.x -
##                6*c10.x*c22.x*c13y3*c23.x + 6*c20.x*c22.x*c13y3*c23.x + 6*c10.y*c13x3*c22.y*c23.y + 2*c12y3*c13.x*c22.x*c23.x -
##                2*c12x3*c13.y*c22.y*c23.y + 6*c10.x*c13.x*c22.x*c13y2*c23.y + 6*c10.x*c13.x*c13y2*c22.y*c23.x +
##                6*c10.y*c13.x*c22.x*c13y2*c23.x - 3*c11.x*c12.x*c22.x*c13y2*c23.y - 3*c11.x*c12.x*c13y2*c22.y*c23.x +
##                2*c11.x*c12.y*c22.x*c13y2*c23.x + 4*c11.y*c12.x*c22.x*c13y2*c23.x - 6*c10.x*c13x2*c13.y*c22.y*c23.y -
##                6*c10.y*c13x2*c22.x*c13.y*c23.y - 6*c10.y*c13x2*c13.y*c22.y*c23.x - 4*c11.x*c12.y*c13x2*c22.y*c23.y -
##                6*c20.x*c13.x*c22.x*c13y2*c23.y - 6*c20.x*c13.x*c13y2*c22.y*c23.x - 2*c11.y*c12.x*c13x2*c22.y*c23.y +
##                3*c11.y*c12.y*c13x2*c22.x*c23.y + 3*c11.y*c12.y*c13x2*c22.y*c23.x - 2*c12.x*c12y2*c13.x*c22.x*c23.y -
##                2*c12.x*c12y2*c13.x*c22.y*c23.x - 2*c12.x*c12y2*c22.x*c13.y*c23.x - 6*c20.y*c13.x*c22.x*c13y2*c23.x -
##                6*c21.x*c13.x*c21.y*c13y2*c23.x - 6*c21.x*c13.x*c22.x*c13y2*c22.y + 6*c20.x*c13x2*c13.y*c22.y*c23.y +
##                2*c12x2*c12.y*c13.x*c22.y*c23.y + 2*c12x2*c12.y*c22.x*c13.y*c23.y + 2*c12x2*c12.y*c13.y*c22.y*c23.x +
##                3*c21.x*c22x2*c13y3 + 3*c21x2*c13y3*c23.x - 3*c13.x*c21.y*c22x2*c13y2 - 3*c21x2*c13.x*c13y2*c23.y +
##                c13x2*c22.x*c13.y*(6*c20.y*c23.y + 6*c21.y*c22.y) + c13x2*c13.y*c23.x*(6*c20.y*c22.y + 3*c21y2) +
##                c21.x*c13x2*c13.y*(6*c21.y*c23.y + 3*c22y2) + c13x3*(-2*c20.y*c22.y*c23.y - c23.y*(2*c20.y*c22.y + c21y2) -
##                c21.y*(2*c21.y*c23.y + c22y2) - c22.y*(2*c20.y*c23.y + 2*c21.y*c22.y)),
##            c11.x*c21.x*c12.y*c13.x*c13.y*c23.y + c11.x*c12.y*c13.x*c21.y*c13.y*c23.x + c11.x*c12.y*c13.x*c22.x*c13.y*c22.y -
##                c11.y*c12.x*c21.x*c13.x*c13.y*c23.y - c11.y*c12.x*c13.x*c21.y*c13.y*c23.x - c11.y*c12.x*c13.x*c22.x*c13.y*c22.y -
##                6*c11.y*c21.x*c12.y*c13.x*c13.y*c23.x - 6*c10.x*c21.x*c13y3*c23.x + 6*c20.x*c21.x*c13y3*c23.x +
##                2*c21.x*c12y3*c13.x*c23.x + 6*c10.x*c21.x*c13.x*c13y2*c23.y + 6*c10.x*c13.x*c21.y*c13y2*c23.x +
##                6*c10.x*c13.x*c22.x*c13y2*c22.y + 6*c10.y*c21.x*c13.x*c13y2*c23.x - 3*c11.x*c12.x*c21.x*c13y2*c23.y -
##                3*c11.x*c12.x*c21.y*c13y2*c23.x - 3*c11.x*c12.x*c22.x*c13y2*c22.y + 2*c11.x*c21.x*c12.y*c13y2*c23.x +
##                4*c11.y*c12.x*c21.x*c13y2*c23.x - 6*c10.y*c21.x*c13x2*c13.y*c23.y - 6*c10.y*c13x2*c21.y*c13.y*c23.x -
##                6*c10.y*c13x2*c22.x*c13.y*c22.y - 6*c20.x*c21.x*c13.x*c13y2*c23.y - 6*c20.x*c13.x*c21.y*c13y2*c23.x -
##                6*c20.x*c13.x*c22.x*c13y2*c22.y + 3*c11.y*c21.x*c12.y*c13x2*c23.y - 3*c11.y*c12.y*c13.x*c22x2*c13.y +
##                3*c11.y*c12.y*c13x2*c21.y*c23.x + 3*c11.y*c12.y*c13x2*c22.x*c22.y - 2*c12.x*c21.x*c12y2*c13.x*c23.y -
##                2*c12.x*c21.x*c12y2*c13.y*c23.x - 2*c12.x*c12y2*c13.x*c21.y*c23.x - 2*c12.x*c12y2*c13.x*c22.x*c22.y -
##                6*c20.y*c21.x*c13.x*c13y2*c23.x - 6*c21.x*c13.x*c21.y*c22.x*c13y2 + 6*c20.y*c13x2*c21.y*c13.y*c23.x +
##                2*c12x2*c21.x*c12.y*c13.y*c23.y + 2*c12x2*c12.y*c21.y*c13.y*c23.x + 2*c12x2*c12.y*c22.x*c13.y*c22.y -
##                3*c10.x*c22x2*c13y3 + 3*c20.x*c22x2*c13y3 + 3*c21x2*c22.x*c13y3 + c12y3*c13.x*c22x2 +
##                3*c10.y*c13.x*c22x2*c13y2 + c11.x*c12.y*c22x2*c13y2 + 2*c11.y*c12.x*c22x2*c13y2 -
##                c12.x*c12y2*c22x2*c13.y - 3*c20.y*c13.x*c22x2*c13y2 - 3*c21x2*c13.x*c13y2*c22.y +
##                c12x2*c12.y*c13.x*(2*c21.y*c23.y + c22y2) + c11.x*c12.x*c13.x*c13.y*(6*c21.y*c23.y + 3*c22y2) +
##                c21.x*c13x2*c13.y*(6*c20.y*c23.y + 6*c21.y*c22.y) + c12x3*c13.y*(-2*c21.y*c23.y - c22y2) +
##                c10.y*c13x3*(6*c21.y*c23.y + 3*c22y2) + c11.y*c12.x*c13x2*(-2*c21.y*c23.y - c22y2) +
##                c11.x*c12.y*c13x2*(-4*c21.y*c23.y - 2*c22y2) + c10.x*c13x2*c13.y*(-6*c21.y*c23.y - 3*c22y2) +
##                c13x2*c22.x*c13.y*(6*c20.y*c22.y + 3*c21y2) + c20.x*c13x2*c13.y*(6*c21.y*c23.y + 3*c22y2) +
##                c13x3*(-2*c20.y*c21.y*c23.y - c22.y*(2*c20.y*c22.y + c21y2) - c20.y*(2*c21.y*c23.y + c22y2) -
##                c21.y*(2*c20.y*c23.y + 2*c21.y*c22.y)),
##            -c10.x*c11.x*c12.y*c13.x*c13.y*c23.y + c10.x*c11.y*c12.x*c13.x*c13.y*c23.y + 6*c10.x*c11.y*c12.y*c13.x*c13.y*c23.x -
##                6*c10.y*c11.x*c12.x*c13.x*c13.y*c23.y - c10.y*c11.x*c12.y*c13.x*c13.y*c23.x + c10.y*c11.y*c12.x*c13.x*c13.y*c23.x +
##                c11.x*c11.y*c12.x*c12.y*c13.x*c23.y - c11.x*c11.y*c12.x*c12.y*c13.y*c23.x + c11.x*c20.x*c12.y*c13.x*c13.y*c23.y +
##                c11.x*c20.y*c12.y*c13.x*c13.y*c23.x + c11.x*c21.x*c12.y*c13.x*c13.y*c22.y + c11.x*c12.y*c13.x*c21.y*c22.x*c13.y -
##                c20.x*c11.y*c12.x*c13.x*c13.y*c23.y - 6*c20.x*c11.y*c12.y*c13.x*c13.y*c23.x - c11.y*c12.x*c20.y*c13.x*c13.y*c23.x -
##                c11.y*c12.x*c21.x*c13.x*c13.y*c22.y - c11.y*c12.x*c13.x*c21.y*c22.x*c13.y - 6*c11.y*c21.x*c12.y*c13.x*c22.x*c13.y -
##                6*c10.x*c20.x*c13y3*c23.x - 6*c10.x*c21.x*c22.x*c13y3 - 2*c10.x*c12y3*c13.x*c23.x + 6*c20.x*c21.x*c22.x*c13y3 +
##                2*c20.x*c12y3*c13.x*c23.x + 2*c21.x*c12y3*c13.x*c22.x + 2*c10.y*c12x3*c13.y*c23.y - 6*c10.x*c10.y*c13.x*c13y2*c23.x +
##                3*c10.x*c11.x*c12.x*c13y2*c23.y - 2*c10.x*c11.x*c12.y*c13y2*c23.x - 4*c10.x*c11.y*c12.x*c13y2*c23.x +
##                3*c10.y*c11.x*c12.x*c13y2*c23.x + 6*c10.x*c10.y*c13x2*c13.y*c23.y + 6*c10.x*c20.x*c13.x*c13y2*c23.y -
##                3*c10.x*c11.y*c12.y*c13x2*c23.y + 2*c10.x*c12.x*c12y2*c13.x*c23.y + 2*c10.x*c12.x*c12y2*c13.y*c23.x +
##                6*c10.x*c20.y*c13.x*c13y2*c23.x + 6*c10.x*c21.x*c13.x*c13y2*c22.y + 6*c10.x*c13.x*c21.y*c22.x*c13y2 +
##                4*c10.y*c11.x*c12.y*c13x2*c23.y + 6*c10.y*c20.x*c13.x*c13y2*c23.x + 2*c10.y*c11.y*c12.x*c13x2*c23.y -
##                3*c10.y*c11.y*c12.y*c13x2*c23.x + 2*c10.y*c12.x*c12y2*c13.x*c23.x + 6*c10.y*c21.x*c13.x*c22.x*c13y2 -
##                3*c11.x*c20.x*c12.x*c13y2*c23.y + 2*c11.x*c20.x*c12.y*c13y2*c23.x + c11.x*c11.y*c12y2*c13.x*c23.x -
##                3*c11.x*c12.x*c20.y*c13y2*c23.x - 3*c11.x*c12.x*c21.x*c13y2*c22.y - 3*c11.x*c12.x*c21.y*c22.x*c13y2 +
##                2*c11.x*c21.x*c12.y*c22.x*c13y2 + 4*c20.x*c11.y*c12.x*c13y2*c23.x + 4*c11.y*c12.x*c21.x*c22.x*c13y2 -
##                2*c10.x*c12x2*c12.y*c13.y*c23.y - 6*c10.y*c20.x*c13x2*c13.y*c23.y - 6*c10.y*c20.y*c13x2*c13.y*c23.x -
##                6*c10.y*c21.x*c13x2*c13.y*c22.y - 2*c10.y*c12x2*c12.y*c13.x*c23.y - 2*c10.y*c12x2*c12.y*c13.y*c23.x -
##                6*c10.y*c13x2*c21.y*c22.x*c13.y - c11.x*c11.y*c12x2*c13.y*c23.y - 2*c11.x*c11y2*c13.x*c13.y*c23.x +
##                3*c20.x*c11.y*c12.y*c13x2*c23.y - 2*c20.x*c12.x*c12y2*c13.x*c23.y - 2*c20.x*c12.x*c12y2*c13.y*c23.x -
##                6*c20.x*c20.y*c13.x*c13y2*c23.x - 6*c20.x*c21.x*c13.x*c13y2*c22.y - 6*c20.x*c13.x*c21.y*c22.x*c13y2 +
##                3*c11.y*c20.y*c12.y*c13x2*c23.x + 3*c11.y*c21.x*c12.y*c13x2*c22.y + 3*c11.y*c12.y*c13x2*c21.y*c22.x -
##                2*c12.x*c20.y*c12y2*c13.x*c23.x - 2*c12.x*c21.x*c12y2*c13.x*c22.y - 2*c12.x*c21.x*c12y2*c22.x*c13.y -
##                2*c12.x*c12y2*c13.x*c21.y*c22.x - 6*c20.y*c21.x*c13.x*c22.x*c13y2 - c11y2*c12.x*c12.y*c13.x*c23.x +
##                2*c20.x*c12x2*c12.y*c13.y*c23.y + 6*c20.y*c13x2*c21.y*c22.x*c13.y + 2*c11x2*c11.y*c13.x*c13.y*c23.y +
##                c11x2*c12.x*c12.y*c13.y*c23.y + 2*c12x2*c20.y*c12.y*c13.y*c23.x + 2*c12x2*c21.x*c12.y*c13.y*c22.y +
##                2*c12x2*c12.y*c21.y*c22.x*c13.y + c21x3*c13y3 + 3*c10x2*c13y3*c23.x - 3*c10y2*c13x3*c23.y +
##                3*c20x2*c13y3*c23.x + c11y3*c13x2*c23.x - c11x3*c13y2*c23.y - c11.x*c11y2*c13x2*c23.y +
##                c11x2*c11.y*c13y2*c23.x - 3*c10x2*c13.x*c13y2*c23.y + 3*c10y2*c13x2*c13.y*c23.x - c11x2*c12y2*c13.x*c23.y +
##                c11y2*c12x2*c13.y*c23.x - 3*c21x2*c13.x*c21.y*c13y2 - 3*c20x2*c13.x*c13y2*c23.y + 3*c20y2*c13x2*c13.y*c23.x +
##                c11.x*c12.x*c13.x*c13.y*(6*c20.y*c23.y + 6*c21.y*c22.y) + c12x3*c13.y*(-2*c20.y*c23.y - 2*c21.y*c22.y) +
##                c10.y*c13x3*(6*c20.y*c23.y + 6*c21.y*c22.y) + c11.y*c12.x*c13x2*(-2*c20.y*c23.y - 2*c21.y*c22.y) +
##                c12x2*c12.y*c13.x*(2*c20.y*c23.y + 2*c21.y*c22.y) + c11.x*c12.y*c13x2*(-4*c20.y*c23.y - 4*c21.y*c22.y) +
##                c10.x*c13x2*c13.y*(-6*c20.y*c23.y - 6*c21.y*c22.y) + c20.x*c13x2*c13.y*(6*c20.y*c23.y + 6*c21.y*c22.y) +
##                c21.x*c13x2*c13.y*(6*c20.y*c22.y + 3*c21y2) + c13x3*(-2*c20.y*c21.y*c22.y - c20y2*c23.y -
##                c21.y*(2*c20.y*c22.y + c21y2) - c20.y*(2*c20.y*c23.y + 2*c21.y*c22.y)),
##            -c10.x*c11.x*c12.y*c13.x*c13.y*c22.y + c10.x*c11.y*c12.x*c13.x*c13.y*c22.y + 6*c10.x*c11.y*c12.y*c13.x*c22.x*c13.y -
##                6*c10.y*c11.x*c12.x*c13.x*c13.y*c22.y - c10.y*c11.x*c12.y*c13.x*c22.x*c13.y + c10.y*c11.y*c12.x*c13.x*c22.x*c13.y +
##                c11.x*c11.y*c12.x*c12.y*c13.x*c22.y - c11.x*c11.y*c12.x*c12.y*c22.x*c13.y + c11.x*c20.x*c12.y*c13.x*c13.y*c22.y +
##                c11.x*c20.y*c12.y*c13.x*c22.x*c13.y + c11.x*c21.x*c12.y*c13.x*c21.y*c13.y - c20.x*c11.y*c12.x*c13.x*c13.y*c22.y -
##                6*c20.x*c11.y*c12.y*c13.x*c22.x*c13.y - c11.y*c12.x*c20.y*c13.x*c22.x*c13.y - c11.y*c12.x*c21.x*c13.x*c21.y*c13.y -
##                6*c10.x*c20.x*c22.x*c13y3 - 2*c10.x*c12y3*c13.x*c22.x + 2*c20.x*c12y3*c13.x*c22.x + 2*c10.y*c12x3*c13.y*c22.y -
##                6*c10.x*c10.y*c13.x*c22.x*c13y2 + 3*c10.x*c11.x*c12.x*c13y2*c22.y - 2*c10.x*c11.x*c12.y*c22.x*c13y2 -
##                4*c10.x*c11.y*c12.x*c22.x*c13y2 + 3*c10.y*c11.x*c12.x*c22.x*c13y2 + 6*c10.x*c10.y*c13x2*c13.y*c22.y +
##                6*c10.x*c20.x*c13.x*c13y2*c22.y - 3*c10.x*c11.y*c12.y*c13x2*c22.y + 2*c10.x*c12.x*c12y2*c13.x*c22.y +
##                2*c10.x*c12.x*c12y2*c22.x*c13.y + 6*c10.x*c20.y*c13.x*c22.x*c13y2 + 6*c10.x*c21.x*c13.x*c21.y*c13y2 +
##                4*c10.y*c11.x*c12.y*c13x2*c22.y + 6*c10.y*c20.x*c13.x*c22.x*c13y2 + 2*c10.y*c11.y*c12.x*c13x2*c22.y -
##                3*c10.y*c11.y*c12.y*c13x2*c22.x + 2*c10.y*c12.x*c12y2*c13.x*c22.x - 3*c11.x*c20.x*c12.x*c13y2*c22.y +
##                2*c11.x*c20.x*c12.y*c22.x*c13y2 + c11.x*c11.y*c12y2*c13.x*c22.x - 3*c11.x*c12.x*c20.y*c22.x*c13y2 -
##                3*c11.x*c12.x*c21.x*c21.y*c13y2 + 4*c20.x*c11.y*c12.x*c22.x*c13y2 - 2*c10.x*c12x2*c12.y*c13.y*c22.y -
##                6*c10.y*c20.x*c13x2*c13.y*c22.y - 6*c10.y*c20.y*c13x2*c22.x*c13.y - 6*c10.y*c21.x*c13x2*c21.y*c13.y -
##                2*c10.y*c12x2*c12.y*c13.x*c22.y - 2*c10.y*c12x2*c12.y*c22.x*c13.y - c11.x*c11.y*c12x2*c13.y*c22.y -
##                2*c11.x*c11y2*c13.x*c22.x*c13.y + 3*c20.x*c11.y*c12.y*c13x2*c22.y - 2*c20.x*c12.x*c12y2*c13.x*c22.y -
##                2*c20.x*c12.x*c12y2*c22.x*c13.y - 6*c20.x*c20.y*c13.x*c22.x*c13y2 - 6*c20.x*c21.x*c13.x*c21.y*c13y2 +
##                3*c11.y*c20.y*c12.y*c13x2*c22.x + 3*c11.y*c21.x*c12.y*c13x2*c21.y - 2*c12.x*c20.y*c12y2*c13.x*c22.x -
##                2*c12.x*c21.x*c12y2*c13.x*c21.y - c11y2*c12.x*c12.y*c13.x*c22.x + 2*c20.x*c12x2*c12.y*c13.y*c22.y -
##                3*c11.y*c21x2*c12.y*c13.x*c13.y + 6*c20.y*c21.x*c13x2*c21.y*c13.y + 2*c11x2*c11.y*c13.x*c13.y*c22.y +
##                c11x2*c12.x*c12.y*c13.y*c22.y + 2*c12x2*c20.y*c12.y*c22.x*c13.y + 2*c12x2*c21.x*c12.y*c21.y*c13.y -
##                3*c10.x*c21x2*c13y3 + 3*c20.x*c21x2*c13y3 + 3*c10x2*c22.x*c13y3 - 3*c10y2*c13x3*c22.y + 3*c20x2*c22.x*c13y3 +
##                c21x2*c12y3*c13.x + c11y3*c13x2*c22.x - c11x3*c13y2*c22.y + 3*c10.y*c21x2*c13.x*c13y2 -
##                c11.x*c11y2*c13x2*c22.y + c11.x*c21x2*c12.y*c13y2 + 2*c11.y*c12.x*c21x2*c13y2 + c11x2*c11.y*c22.x*c13y2 -
##                c12.x*c21x2*c12y2*c13.y - 3*c20.y*c21x2*c13.x*c13y2 - 3*c10x2*c13.x*c13y2*c22.y + 3*c10y2*c13x2*c22.x*c13.y -
##                c11x2*c12y2*c13.x*c22.y + c11y2*c12x2*c22.x*c13.y - 3*c20x2*c13.x*c13y2*c22.y + 3*c20y2*c13x2*c22.x*c13.y +
##                c12x2*c12.y*c13.x*(2*c20.y*c22.y + c21y2) + c11.x*c12.x*c13.x*c13.y*(6*c20.y*c22.y + 3*c21y2) +
##                c12x3*c13.y*(-2*c20.y*c22.y - c21y2) + c10.y*c13x3*(6*c20.y*c22.y + 3*c21y2) +
##                c11.y*c12.x*c13x2*(-2*c20.y*c22.y - c21y2) + c11.x*c12.y*c13x2*(-4*c20.y*c22.y - 2*c21y2) +
##                c10.x*c13x2*c13.y*(-6*c20.y*c22.y - 3*c21y2) + c20.x*c13x2*c13.y*(6*c20.y*c22.y + 3*c21y2) +
##                c13x3*(-2*c20.y*c21y2 - c20y2*c22.y - c20.y*(2*c20.y*c22.y + c21y2)),
##            -c10.x*c11.x*c12.y*c13.x*c21.y*c13.y + c10.x*c11.y*c12.x*c13.x*c21.y*c13.y + 6*c10.x*c11.y*c21.x*c12.y*c13.x*c13.y -
##                6*c10.y*c11.x*c12.x*c13.x*c21.y*c13.y - c10.y*c11.x*c21.x*c12.y*c13.x*c13.y + c10.y*c11.y*c12.x*c21.x*c13.x*c13.y -
##                c11.x*c11.y*c12.x*c21.x*c12.y*c13.y + c11.x*c11.y*c12.x*c12.y*c13.x*c21.y + c11.x*c20.x*c12.y*c13.x*c21.y*c13.y +
##                6*c11.x*c12.x*c20.y*c13.x*c21.y*c13.y + c11.x*c20.y*c21.x*c12.y*c13.x*c13.y - c20.x*c11.y*c12.x*c13.x*c21.y*c13.y -
##                6*c20.x*c11.y*c21.x*c12.y*c13.x*c13.y - c11.y*c12.x*c20.y*c21.x*c13.x*c13.y - 6*c10.x*c20.x*c21.x*c13y3 -
##                2*c10.x*c21.x*c12y3*c13.x + 6*c10.y*c20.y*c13x3*c21.y + 2*c20.x*c21.x*c12y3*c13.x + 2*c10.y*c12x3*c21.y*c13.y -
##                2*c12x3*c20.y*c21.y*c13.y - 6*c10.x*c10.y*c21.x*c13.x*c13y2 + 3*c10.x*c11.x*c12.x*c21.y*c13y2 -
##                2*c10.x*c11.x*c21.x*c12.y*c13y2 - 4*c10.x*c11.y*c12.x*c21.x*c13y2 + 3*c10.y*c11.x*c12.x*c21.x*c13y2 +
##                6*c10.x*c10.y*c13x2*c21.y*c13.y + 6*c10.x*c20.x*c13.x*c21.y*c13y2 - 3*c10.x*c11.y*c12.y*c13x2*c21.y +
##                2*c10.x*c12.x*c21.x*c12y2*c13.y + 2*c10.x*c12.x*c12y2*c13.x*c21.y + 6*c10.x*c20.y*c21.x*c13.x*c13y2 +
##                4*c10.y*c11.x*c12.y*c13x2*c21.y + 6*c10.y*c20.x*c21.x*c13.x*c13y2 + 2*c10.y*c11.y*c12.x*c13x2*c21.y -
##                3*c10.y*c11.y*c21.x*c12.y*c13x2 + 2*c10.y*c12.x*c21.x*c12y2*c13.x - 3*c11.x*c20.x*c12.x*c21.y*c13y2 +
##                2*c11.x*c20.x*c21.x*c12.y*c13y2 + c11.x*c11.y*c21.x*c12y2*c13.x - 3*c11.x*c12.x*c20.y*c21.x*c13y2 +
##                4*c20.x*c11.y*c12.x*c21.x*c13y2 - 6*c10.x*c20.y*c13x2*c21.y*c13.y - 2*c10.x*c12x2*c12.y*c21.y*c13.y -
##                6*c10.y*c20.x*c13x2*c21.y*c13.y - 6*c10.y*c20.y*c21.x*c13x2*c13.y - 2*c10.y*c12x2*c21.x*c12.y*c13.y -
##                2*c10.y*c12x2*c12.y*c13.x*c21.y - c11.x*c11.y*c12x2*c21.y*c13.y - 4*c11.x*c20.y*c12.y*c13x2*c21.y -
##                2*c11.x*c11y2*c21.x*c13.x*c13.y + 3*c20.x*c11.y*c12.y*c13x2*c21.y - 2*c20.x*c12.x*c21.x*c12y2*c13.y -
##                2*c20.x*c12.x*c12y2*c13.x*c21.y - 6*c20.x*c20.y*c21.x*c13.x*c13y2 - 2*c11.y*c12.x*c20.y*c13x2*c21.y +
##                3*c11.y*c20.y*c21.x*c12.y*c13x2 - 2*c12.x*c20.y*c21.x*c12y2*c13.x - c11y2*c12.x*c21.x*c12.y*c13.x +
##                6*c20.x*c20.y*c13x2*c21.y*c13.y + 2*c20.x*c12x2*c12.y*c21.y*c13.y + 2*c11x2*c11.y*c13.x*c21.y*c13.y +
##                c11x2*c12.x*c12.y*c21.y*c13.y + 2*c12x2*c20.y*c21.x*c12.y*c13.y + 2*c12x2*c20.y*c12.y*c13.x*c21.y +
##                3*c10x2*c21.x*c13y3 - 3*c10y2*c13x3*c21.y + 3*c20x2*c21.x*c13y3 + c11y3*c21.x*c13x2 - c11x3*c21.y*c13y2 -
##                3*c20y2*c13x3*c21.y - c11.x*c11y2*c13x2*c21.y + c11x2*c11.y*c21.x*c13y2 - 3*c10x2*c13.x*c21.y*c13y2 +
##                3*c10y2*c21.x*c13x2*c13.y - c11x2*c12y2*c13.x*c21.y + c11y2*c12x2*c21.x*c13.y - 3*c20x2*c13.x*c21.y*c13y2 +
##                3*c20y2*c21.x*c13x2*c13.y,
##            c10.x*c10.y*c11.x*c12.y*c13.x*c13.y - c10.x*c10.y*c11.y*c12.x*c13.x*c13.y + c10.x*c11.x*c11.y*c12.x*c12.y*c13.y -
##                c10.y*c11.x*c11.y*c12.x*c12.y*c13.x - c10.x*c11.x*c20.y*c12.y*c13.x*c13.y + 6*c10.x*c20.x*c11.y*c12.y*c13.x*c13.y +
##                c10.x*c11.y*c12.x*c20.y*c13.x*c13.y - c10.y*c11.x*c20.x*c12.y*c13.x*c13.y - 6*c10.y*c11.x*c12.x*c20.y*c13.x*c13.y +
##                c10.y*c20.x*c11.y*c12.x*c13.x*c13.y - c11.x*c20.x*c11.y*c12.x*c12.y*c13.y + c11.x*c11.y*c12.x*c20.y*c12.y*c13.x +
##                c11.x*c20.x*c20.y*c12.y*c13.x*c13.y - c20.x*c11.y*c12.x*c20.y*c13.x*c13.y - 2*c10.x*c20.x*c12y3*c13.x +
##                2*c10.y*c12x3*c20.y*c13.y - 3*c10.x*c10.y*c11.x*c12.x*c13y2 - 6*c10.x*c10.y*c20.x*c13.x*c13y2 +
##                3*c10.x*c10.y*c11.y*c12.y*c13x2 - 2*c10.x*c10.y*c12.x*c12y2*c13.x - 2*c10.x*c11.x*c20.x*c12.y*c13y2 -
##                c10.x*c11.x*c11.y*c12y2*c13.x + 3*c10.x*c11.x*c12.x*c20.y*c13y2 - 4*c10.x*c20.x*c11.y*c12.x*c13y2 +
##                3*c10.y*c11.x*c20.x*c12.x*c13y2 + 6*c10.x*c10.y*c20.y*c13x2*c13.y + 2*c10.x*c10.y*c12x2*c12.y*c13.y +
##                2*c10.x*c11.x*c11y2*c13.x*c13.y + 2*c10.x*c20.x*c12.x*c12y2*c13.y + 6*c10.x*c20.x*c20.y*c13.x*c13y2 -
##                3*c10.x*c11.y*c20.y*c12.y*c13x2 + 2*c10.x*c12.x*c20.y*c12y2*c13.x + c10.x*c11y2*c12.x*c12.y*c13.x +
##                c10.y*c11.x*c11.y*c12x2*c13.y + 4*c10.y*c11.x*c20.y*c12.y*c13x2 - 3*c10.y*c20.x*c11.y*c12.y*c13x2 +
##                2*c10.y*c20.x*c12.x*c12y2*c13.x + 2*c10.y*c11.y*c12.x*c20.y*c13x2 + c11.x*c20.x*c11.y*c12y2*c13.x -
##                3*c11.x*c20.x*c12.x*c20.y*c13y2 - 2*c10.x*c12x2*c20.y*c12.y*c13.y - 6*c10.y*c20.x*c20.y*c13x2*c13.y -
##                2*c10.y*c20.x*c12x2*c12.y*c13.y - 2*c10.y*c11x2*c11.y*c13.x*c13.y - c10.y*c11x2*c12.x*c12.y*c13.y -
##                2*c10.y*c12x2*c20.y*c12.y*c13.x - 2*c11.x*c20.x*c11y2*c13.x*c13.y - c11.x*c11.y*c12x2*c20.y*c13.y +
##                3*c20.x*c11.y*c20.y*c12.y*c13x2 - 2*c20.x*c12.x*c20.y*c12y2*c13.x - c20.x*c11y2*c12.x*c12.y*c13.x +
##                3*c10y2*c11.x*c12.x*c13.x*c13.y + 3*c11.x*c12.x*c20y2*c13.x*c13.y + 2*c20.x*c12x2*c20.y*c12.y*c13.y -
##                3*c10x2*c11.y*c12.y*c13.x*c13.y + 2*c11x2*c11.y*c20.y*c13.x*c13.y + c11x2*c12.x*c20.y*c12.y*c13.y -
##                3*c20x2*c11.y*c12.y*c13.x*c13.y - c10x3*c13y3 + c10y3*c13x3 + c20x3*c13y3 - c20y3*c13x3 -
##                3*c10.x*c20x2*c13y3 - c10.x*c11y3*c13x2 + 3*c10x2*c20.x*c13y3 + c10.y*c11x3*c13y2 +
##                3*c10.y*c20y2*c13x3 + c20.x*c11y3*c13x2 + c10x2*c12y3*c13.x - 3*c10y2*c20.y*c13x3 - c10y2*c12x3*c13.y +
##                c20x2*c12y3*c13.x - c11x3*c20.y*c13y2 - c12x3*c20y2*c13.y - c10.x*c11x2*c11.y*c13y2 +
##                c10.y*c11.x*c11y2*c13x2 - 3*c10.x*c10y2*c13x2*c13.y - c10.x*c11y2*c12x2*c13.y + c10.y*c11x2*c12y2*c13.x -
##                c11.x*c11y2*c20.y*c13x2 + 3*c10x2*c10.y*c13.x*c13y2 + c10x2*c11.x*c12.y*c13y2 +
##                2*c10x2*c11.y*c12.x*c13y2 - 2*c10y2*c11.x*c12.y*c13x2 - c10y2*c11.y*c12.x*c13x2 + c11x2*c20.x*c11.y*c13y2 -
##                3*c10.x*c20y2*c13x2*c13.y + 3*c10.y*c20x2*c13.x*c13y2 + c11.x*c20x2*c12.y*c13y2 - 2*c11.x*c20y2*c12.y*c13x2 +
##                c20.x*c11y2*c12x2*c13.y - c11.y*c12.x*c20y2*c13x2 - c10x2*c12.x*c12y2*c13.y - 3*c10x2*c20.y*c13.x*c13y2 +
##                3*c10y2*c20.x*c13x2*c13.y + c10y2*c12x2*c12.y*c13.x - c11x2*c20.y*c12y2*c13.x + 2*c20x2*c11.y*c12.x*c13y2 +
##                3*c20.x*c20y2*c13x2*c13.y - c20x2*c12.x*c12y2*c13.y - 3*c20x2*c20.y*c13.x*c13y2 + c12x2*c20y2*c12.y*c13.x
##            ]
##    roots = poly.getRootsInInterval(0,1);
##    #
##    for i in range(len(roots)): #( var i = 0; i < roots.length; i++ ) {
##        s = roots[i]
##        xRoots = [c13.x,
##                  c12.x,
##                  c11.x,
##                  c10.x - c20.x - s*c21.x - s*s*c22.x - s*s*s*c23.x
##                  ].getRoots()
##        yRoots = [c13.y,
##                  c12.y,
##                  c11.y,
##                  c10.y - c20.y - s*c21.y - s*s*c22.y - s*s*s*c23.y
##                  ].getRoots()
##
##        if ( len(xRoots) > 0 and len(yRoots) > 0 ):
##            TOLERANCE = 1e-4;
##            #label:checkRoots
##            #
##            for j in range(len(xRoots): #( var j = 0; j < xRoots.length; j++ ) {
##                xRoot = xRoots[j]
##                #
##                if ( 0 <= xRoot and xRoot <= 1 ) {
##                    for k in range(len(yRoots)): #( var k = 0; k < yRoots.length; k++ ) {
##                        if ( math.abs( xRoot - yRoots[k] ) < TOLERANCE ):
##                            result.points.push( c23.multiply(s*s*s).add(c22.multiply(s*s).add(c21.multiply(s).add(c20))))
##                            break #checkRoots;
##    #
##    if ( result.points.length > 0 ): result.status = "Intersection";
##    return result




    
    
###
class LasercutJigsaw(inkex.Effect):

    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("-x", "--width",
                        action="store", type="float",
                        dest="width", default=50.0,
                        help="The Box Width - in the X dimension")
        self.OptionParser.add_option("-y", "--height",
                        action="store", type="float",
                        dest="height", default=30.0,
                        help="The Box Height - in the Y dimension")
        self.OptionParser.add_option("-u", "--units",
                        action="store", type="string",
                        dest="units", default="cm",
                        help="The unit of the box dimensions")
        self.OptionParser.add_option("-w", "--pieces_W",
                        action="store", type="int",
                        dest="pieces_W", default=11,
                        help="How many pieces across")
        self.OptionParser.add_option("-z", "--pieces_H",
                        action="store", type="int",
                        dest="pieces_H", default=11,
                        help="How many pieces down")
        self.OptionParser.add_option("-k", "--notch_percent",
                        action="store", type="float",
                        dest="notch_percent", default=0.0,
                        help="Notch relative size. 0 to 1. 0.15 is good")
        self.OptionParser.add_option("-r", "--rand",
                        action="store", type="float",
                        dest="rand", default=0.1,
                        help="Amount to perturb the basic piece grid.")
        self.OptionParser.add_option("-i", "--innerradius",
                        action="store", type="float",
                        dest="innerradius", default=5.0,
                        help="0 implies square corners")
        self.OptionParser.add_option("-b", "--border",
                        action="store", type="inkbool",
                        dest="border", default=False,
                        help="Add Outer Surround")
        self.OptionParser.add_option("-a", "--borderwidth",
                        action="store", type="float",
                        dest="borderwidth", default=10.0,
                        help="Size of external surrounding border.")
        self.OptionParser.add_option("-o", "--outerradius",
                        action="store", type="float",
                        dest="outerradius", default=5.0,
                        help="0 implies square corners")
        self.OptionParser.add_option("-p", "--pack",
                        action="store", type="string",
                        dest="pack", default="Below",
                        help="Where to place backing piece on page")
        self.OptionParser.add_option("-g", "--use_seed",
                        action="store", type="inkbool",
                        dest="use_seed", default=False,
                        help="Use the kerf value as the drawn line width")
        self.OptionParser.add_option("-s", "--seed",
                        action="store", type="int",
                        dest="seed", default=12345,
                        help="Random seed for repeatability")
        self.OptionParser.add_option("-j", "--pieces",
                        action="store", type="inkbool",
                        dest="pieces", default=False,
                        help="Make extra pieces for manual boolean separation.")
        # dummy for the doc tab - which is named
        self.OptionParser.add_option("--tab",
                        action="store", type="string", 
                        dest="tab", default="use",
                        help="The selected UI-tab when OK was pressed")
        # internal useful variables
        self.stroke_width = 0.1 # default for visiblity
        self.line_style = {'stroke': '#0000FF', # Ponoko blue
                           'fill': 'none',
                           'stroke-width': self.stroke_width,
                           'stroke-linecap': 'butt',
                           'stroke-linejoin': 'miter'}


    def add_jigsaw_horiz_line(self, startx, starty, stepx, steps, width, style, name, parent):
        """ complex version All C smooth
            - get ctrl pt offset and use on both sides of each node (negate for smooth)"""
        line_path = []
        # starts with an M - then C with first point same as M = smooth (also last point still in C but doubled)
        line_path.append(['M', [startx, starty]])
        clist = [startx, starty] # duplicate 1st point so its smooth
        for i in range(1,steps+1):
            flip = 1
            if random.uniform(0.0,1.0) < 0.5:
                flip = -1
            pt1 = randomize((startx-self.notch_step+i*stepx/2+stepx/2*(i-1), starty+self.notch_step/4*flip), self.random_radius/3, True)
            pt2 = randomize((startx-self.notch_step+i*stepx/2+stepx/2*(i-1), starty-self.notch_step*flip), self.random_radius/3, True)
            # pt3 is foor tip of the notch - required ?
            pt4 = randomize((startx+self.notch_step+i*stepx/2+stepx/2*(i-1), starty-self.notch_step*flip), self.random_radius/3, True) #mirror of 2
            pt5 = randomize((startx+self.notch_step+i*stepx/2+stepx/2*(i-1), starty+self.notch_step/4*flip), self.random_radius/3, True) # mirror of pt1
            # Create random local value for x,y of handle - then reflect to enforce smoothness
            rand1 = randomize((0, 0), self.random_radius/4, True, True)
            rand2 = randomize((0, 0), self.random_radius/4, True, True)
            rand4 = randomize((0, 0), self.random_radius/4, True, True)
            rand5 = randomize((0, 0), self.random_radius/4, True, True)
            # up to pt1
            #ctrl1_2 = (startx+i*stepx/2+(i-1)*stepx/2, starty-self.notch_step/3)
            ctrl1 = (self.notch_step/1.2, -self.notch_step/3)
            clist.extend([pt1[0]-ctrl1[0]-rand1[0], pt1[1]-ctrl1[1]*flip+rand1[1]*flip])
            clist.extend(pt1)
            # up to pt2
            clist.extend([pt1[0]+ctrl1[0]+rand1[0], pt1[1]+ctrl1[1]*flip-rand1[1]*flip])
            ctrl2 = (0, -self.notch_step/1.2)
            clist.extend([pt2[0]+ctrl2[0]-rand2[0], pt2[1]-ctrl2[1]*flip+rand2[1]*flip])
            clist.extend(pt2)
            # up to pt4
            clist.extend([pt2[0]-ctrl2[0]+rand2[0], pt2[1]+ctrl2[1]*flip-rand2[1]*flip])
            ctrl4 = (0, self.notch_step/1.2)
            clist.extend([pt4[0]+ctrl4[0]-rand4[0], pt4[1]-ctrl4[1]*flip+rand4[1]*flip])
            clist.extend(pt4)
            # up to pt5
            clist.extend([pt4[0]-ctrl4[0]+rand4[0], pt4[1]+ctrl4[1]*flip-rand4[1]*flip])
            ctrl5 = (self.notch_step/1.2, self.notch_step/3)
            clist.extend([pt5[0]-ctrl5[0]+rand5[0], pt5[1]-ctrl5[1]*flip-rand5[1]*flip])
            clist.extend(pt5)
            # last ctrl point for next step
            clist.extend([pt5[0]+ctrl5[0]-rand5[0], pt5[1]+ctrl5[1]*flip+rand5[1]*flip])        
        #
        clist.extend([width, starty, width, starty]) # doubled up at end for smooth curve
        line_path.append(['C',clist])
        #sys.stderr.write("%s\n"% line_path)
        line_style = simplestyle.formatStyle(style)
        attribs = { 'style':line_style, 'id':name, 'd':formatPath(line_path) }
        inkex.etree.SubElement(parent, inkex.addNS('path','svg'), attribs )

    def create_horiz_blocks(self, group, gridy, style):
        path = lastpath = 0
        blocks = []
        count = 0
        for node in gridy.iterchildren():
            if node.tag == inkex.addNS('path','svg'): # which they ALL should because we just made them
                path = cubicsuperpath.parsePath(node.get('d')) # turn it into a global C style SVG path
                #sys.stderr.write("count: %d\n"% count)
                if count == 0: # first one so use the top border
                    spath = node.get('d') # work on string instead of cubicpath
                    lastpoint = spath.split()[-2:]
                    lastx = float(lastpoint[0])
                    lasty = float(lastpoint[1])
                    #sys.stderr.write("lastpoint: %s\n"% lastpoint)
                    spath += ' %f %f %f %f %f %f' % (lastx,lasty-self.inner_radius, lastx,1.5*self.inner_radius, lastx,self.inner_radius)
                    spath += ' %f %f %f %f %f %f' % (self.width,self.inner_radius/2, self.width-self.inner_radius/2,0, self.width-self.inner_radius,0)
                    spath += ' %f %f %f %f %f %f' % (self.width-self.inner_radius/2,0, 1.5*self.inner_radius,0, self.inner_radius, 0)
                    spath += ' %f %f %f %f %f %f' % (self.inner_radius/2, 0, 0,self.inner_radius/2, 0,self.inner_radius)
                    spath += 'z'
                    #sys.stderr.write("spath: %s\n"% spath)
                    #
                    name = "RowPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':spath }
                    n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                else: # internal line - concat a reversed version with the last one
                    thispath = copy.deepcopy(path)
                    for i in range(len(thispath[0])): # reverse the internal C pairs
                        thispath[0][i].reverse()
                    thispath[0].reverse() # reverse the entire line
                    lastpath[0].extend(thispath[0]) # append
                    name = "RowPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':cubicsuperpath.formatPath(lastpath) }
                    n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                    n.set('d', n.get('d')+'z') # close it
                #
                count += 1
                lastpath = path
        # do the last row
        spath = node.get('d') # work on string instead of cubicpath
        lastpoint = spath.split()[-2:]
        lastx = float(lastpoint[0])
        lasty = float(lastpoint[1])
        #sys.stderr.write("lastpoint: %s\n"% lastpoint)
        spath += ' %f %f %f %f %f %f' % (lastx,lasty+self.inner_radius, lastx,self.height-1.5*self.inner_radius, lastx,self.height-self.inner_radius)
        spath += ' %f %f %f %f %f %f' % (self.width,self.height-self.inner_radius/2, self.width-self.inner_radius/2,self.height, self.width-self.inner_radius,self.height)
        spath += ' %f %f %f %f %f %f' % (self.width-self.inner_radius/2,self.height, 1.5*self.inner_radius,self.height, self.inner_radius, self.height)
        spath += ' %f %f %f %f %f %f' % (self.inner_radius/2, self.height, 0,self.height-self.inner_radius/2, 0,self.height-self.inner_radius)
        spath += 'z'
        #
        name = "RowPieces_%d" % (count)
        attribs = { 'style':style, 'id':name, 'd':spath }
        n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
        blocks.append(n) # for direct traversal later
        #
        return(blocks)
    

    def create_vert_blocks(self, group, gridx, style):
        path = lastpath = 0
        blocks = []
        count = 0
        for node in gridx.iterchildren():
            if node.tag == inkex.addNS('path','svg'): # which they ALL should because we just made them
                path = cubicsuperpath.parsePath(node.get('d')) # turn it into a global C style SVG path
                #sys.stderr.write("count: %d\n"% count)
                if count == 0: # first one so use the right border
                    spath = node.get('d') # work on string instead of cubicpath
                    lastpoint = spath.split()[-2:]
                    lastx = float(lastpoint[0])
                    lasty = float(lastpoint[1])
                    #sys.stderr.write("lastpoint: %s\n"% lastpoint)
                    spath += ' %f %f %f %f %f %f' % (lastx+self.inner_radius/2,lasty, self.width-1.5*self.inner_radius,lasty, self.width-self.inner_radius, lasty)
                    spath += ' %f %f %f %f %f %f' % (self.width-self.inner_radius/2,lasty, self.width,self.height-self.inner_radius/2, self.width,self.height-self.inner_radius)
                    spath += ' %f %f %f %f %f %f' % (self.width,self.height-1.5*self.inner_radius, self.width, 1.5*self.inner_radius, self.width,self.inner_radius)
                    spath += ' %f %f %f %f %f %f' % (self.width,self.inner_radius/2, self.width-self.inner_radius/2,0, self.width-self.inner_radius,0)
                    spath += 'z'
                    #sys.stderr.write("spath: %s\n"% spath)
                    #
                    name = "ColPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':spath }
                    n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                else: # internal line - concat a reversed version with the last one
                    thispath = copy.deepcopy(path)
                    for i in range(len(thispath[0])): # reverse the internal C pairs
                        thispath[0][i].reverse()
                    thispath[0].reverse() # reverse the entire line
                    lastpath[0].extend(thispath[0]) # append
                    name = "ColPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':cubicsuperpath.formatPath(lastpath) }
                    n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                    n.set('d', n.get('d')+'z') # close it
                #
                count += 1
                lastpath = path
        # do the last one (LHS)
        spath = node.get('d') # work on string instead of cubicpath
        lastpoint = spath.split()[-2:]
        lastx = float(lastpoint[0])
        lasty = float(lastpoint[1])
        #sys.stderr.write("lastpoint: %s\n"% lastpoint)
        spath += ' %f %f %f %f %f %f' % (lastx-self.inner_radius,lasty, 1.5*self.inner_radius, lasty, self.inner_radius,lasty)
        spath += ' %f %f %f %f %f %f' % (self.inner_radius/2,lasty, 0,lasty-self.inner_radius/2, 0,lasty-self.inner_radius)
        spath += ' %f %f %f %f %f %f' % (0,lasty-1.5*self.inner_radius, 0,1.5*self.inner_radius, 0,self.inner_radius)
        spath += ' %f %f %f %f %f %f' % (self.inner_radius/2,0, self.inner_radius,0, 1.5*self.inner_radius, 0)
        spath += 'z'
        #
        name = "ColPieces_%d" % (count)
        attribs = { 'style':style, 'id':name, 'd':spath }
        n = inkex.etree.SubElement(group, inkex.addNS('path','svg'), attribs )
        blocks.append(n) # for direct traversal later
        #
        return(blocks)

    
    def create_pieces(self, jigsaw, gridx, gridy):
        """ Loop through each row """
        # Treat outer edge carefully as border runs around. So special code the edges
        # Internal lines should be in pairs  -with second line reversed and appended to first. Close with a 'z'
        # Create new group
        g_attribs = {inkex.addNS('label','inkscape'):'JigsawPieces:X' + \
                     str( self.pieces_W )+':Y'+str( self.pieces_H ) }
        jigsaw_pieces = inkex.etree.SubElement(jigsaw, 'g', g_attribs)
        line_style = simplestyle.formatStyle(self.line_style)
        #
        xblocks = self.create_horiz_blocks(jigsaw_pieces, gridy, line_style)
        #sys.stderr.write("count: %s\n"% dir(gridx))
        yblocks = self.create_vert_blocks(jigsaw_pieces, gridx, line_style)
        #
        # for each xblock intersect it with each Y block
        #for x in range(len(xblocks)):
        #    for y in range(len(yblocks)):
                
        # delete the paths in xblocks and yblocks
        # transform them out of the way for now
        for node in xblocks:
            node.set('transform', 'translate(%f,%f)' % (self.width, 0))
            simpletransform.fuseTransform(node)
        for node in yblocks:
            node.set('transform', 'translate(%f,%f)' % (self.width, 0))
            simpletransform.fuseTransform(node)

        
    ###--------------------------------------------
    ### The main function called by the Inkscape UI
    def effect(self):
        # document dimensions (for centering)
        docW = self.unittouu(self.document.getroot().get('width'))
        docH = self.unittouu(self.document.getroot().get('height'))
        # extract fields from UI
        self.width  = self.unittouu( str(self.options.width)  + self.options.units )
        self.height  = self.unittouu( str(self.options.height) + self.options.units )
        self.pieces_W = self.options.pieces_W
        self.pieces_H = self.options.pieces_H
        average_block = (self.width/self.pieces_W + self.height/self.pieces_H) / 2
        self.notch_step = average_block * self.options.notch_percent / 3 # 3 = a useful notch size factor
        self.random_radius = self.options.rand * average_block / 5 # 5 = a useful range factor
        self.inner_radius = self.options.innerradius
        if self.inner_radius < 0.01: self.inner_radius = 0.0 # snap to 0 for UI error when setting spinner to 0.0
        self.border = self.options.border
        self.borderwidth = self.options.borderwidth
        self.outer_radius = self.options.outerradius
        if self.outer_radius < 0.01: self.outer_radius = 0.0 # snap to 0 for UI error when setting spinner to 0.0
        self.pack = self.options.pack
        # pieces
        self.pieces = self.options.pieces
        # random function
        if not self.options.use_seed:
            random.seed(self.options.seed)
        
        #
        # set up the main object in the current layer - group gridlines
        g_attribs = {inkex.addNS('label','inkscape'):'Jigsaw:X' + \
                     str( self.pieces_W )+':Y'+str( self.pieces_H ) }
        jigsaw_group = inkex.etree.SubElement(self.current_layer, 'g', g_attribs)
        #Group for X grid
        g_attribs = {inkex.addNS('label','inkscape'):'X_Gridlines'}
        gridx = inkex.etree.SubElement(jigsaw_group, 'g', g_attribs)
        #Group for Y grid
        g_attribs = {inkex.addNS('label','inkscape'):'Y_Gridlines'}
        gridy = inkex.etree.SubElement(jigsaw_group, 'g', g_attribs)

        # Draw the Border
        add_rounded_rectangle(0,0, self.inner_radius, self.width, self.height, self.line_style, 'innerborder', jigsaw_group)
        # Do the Border
        if self.border:
            add_rounded_rectangle(-self.borderwidth,-self.borderwidth, self.outer_radius, self.borderwidth*2+self.width,
                                  self.borderwidth*2+self.height, self.line_style, 'outerborder', jigsaw_group)
            # make a second copy below the jigsaw for the cutout BG
            if self.pack == "Below":
                add_rounded_rectangle(-self.borderwidth,self.borderwidth+ self.height, self.outer_radius, self.borderwidth*2+self.width,
                                      self.borderwidth*2+self.height, self.line_style, 'BG', jigsaw_group, self.pack)
            elif self.pack == "Right":
                add_rounded_rectangle(self.width+self.borderwidth,-self.borderwidth, self.outer_radius, self.borderwidth*2+self.width,
                                      self.borderwidth*2+self.height, self.line_style, 'BG', jigsaw_group, self.pack)
            else: # Separate
                add_rounded_rectangle(self.width+self.borderwidth*2,-self.borderwidth, self.outer_radius, self.borderwidth*2+self.width,
                                      self.borderwidth*2+self.height, self.line_style, 'BG', jigsaw_group)

        # Step through the Grid
        Xstep = self.width / (self.pieces_W)
        Ystep = self.height / (self.pieces_H)
        # Draw Horizontal lines on Y step with Xstep notches
        for i in range(1, self.pieces_H):
            self.add_jigsaw_horiz_line(0, Ystep*i, Xstep, self.pieces_W, self.width, self.line_style, 'YDiv'+str(i), gridy)
        # Draw Vertical lines on X step with Ystep notches
        for i in range(1, self.pieces_W):
            self.add_jigsaw_horiz_line(0, Xstep*i, Ystep, self.pieces_H, self.height, self.line_style, 'XDiv'+str(i), gridx)
        # Rotate lines into pos
        # actualy transform can have multiple transforms in it e.g. 'translate(10,10) rotate(10)'
        for node in gridx.iterchildren():
            if node.tag == inkex.addNS('path','svg'):
                node.set('transform', 'rotate(%d)' % 90)
                simpletransform.fuseTransform(node)
                node.set('transform', 'translate(%f,%f)' % (self.width, 0))
                simpletransform.fuseTransform(node)
        # center the jigsaw
        jigsaw_group.set('transform', 'translate(%f,%f)' % ( (docW-self.width)/2, (docH-self.height)/2 ) )
        
        # pieces
        if self.pieces:
            self.create_pieces(jigsaw_group, gridx,gridy)
            # needs manual boolean ops until that is exposed or we get all the commented code working up top :-(
        

###
if __name__ == '__main__':
    e = LasercutJigsaw()
    e.affect()
