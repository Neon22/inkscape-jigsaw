#!/usr/bin/env python3
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
### 0.3 add some no-knob edges - June 2019

### Todo
# add option to cut pieces:
#    - taking two rows(cols) at a time - reverse the second one and concat on end - add z to close
#    - taking a row and a col - do intersect = piece.

__version__ = "0.4"

import inkex
import sys, math, random, copy
from lxml import etree
from inkex.paths import Path, CubicSuperPath

def dirtyFormat(path):
    return str(path).replace('[','').replace(']','').replace(',','').replace('\'','')
          
def randomize(x_y, radius, norm=True, absolute=False):
    """ return x,y moved by a random amount inside a radius.
        use uniform distribution unless
         - norm = True - then use a normal distribution
        If absolute is true - ensure random is only added to x,y  """
    # if norm:
        # r = abs(random.normalvariate(0.0,0.5*radius))
    # else:
        # r = random.uniform(0.0,radius)
    x, y = x_y
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
    attribs = {'style':str(inkex.Style(style)), inkex.addNS('label','inkscape'):name, 'd':dirtyFormat(line_path)}
    #sys.stderr.write("%s\n"% attribs)
    etree.SubElement(parent, inkex.addNS('path','svg'), attribs )

###----------------------
### all for intersection  from http://www.kevlindev.com/gui/index.htm

def get_derivative(polynomial):
    deriv = []
    for i in range(len(polynomial)):
        deriv.append(i* polynomial[i])
    return deriv

class LasercutJigsaw(inkex.Effect):

    def __init__(self):
        inkex.Effect.__init__(self)
        self.arg_parser.add_argument("-x", "--width", type=float, default=50.0, help="The Box Width - in the X dimension")
        self.arg_parser.add_argument("-y", "--height", type=float, default=30.0, help="The Box Height - in the Y dimension")
        self.arg_parser.add_argument("-u", "--units", type=str, default="cm", help="The unit of the box dimensions")
        self.arg_parser.add_argument("-w", "--pieces_W", type=int, default=11, help="How many pieces across")
        self.arg_parser.add_argument("-z", "--pieces_H", type=int, default=11, help="How many pieces down")
        self.arg_parser.add_argument("-k", "--notch_percent", type=float, default=0.0, help="Notch relative size. 0 to 1. 0.15 is good")
        self.arg_parser.add_argument("-r", "--rand", type=float, default=0.1, help="Amount to perturb the basic piece grid.")
        self.arg_parser.add_argument("-i", "--innerradius", type=float, default=5.0, help="0 implies square corners")
        self.arg_parser.add_argument("-b", "--border", type=inkex.Boolean, default=False, help="Add Outer Surround")
        self.arg_parser.add_argument("-a", "--borderwidth", type=float, default=10.0, help="Size of external surrounding border.")
        self.arg_parser.add_argument("-o", "--outerradius", type=float, default=5.0, help="0 implies square corners")
        self.arg_parser.add_argument("-p", "--pack", type=str, default="Below", help="Where to place backing piece on page")
        self.arg_parser.add_argument("-g", "--use_seed", type=inkex.Boolean, default=False, help="Use the kerf value as the drawn line width")
        self.arg_parser.add_argument("-s", "--seed", type=int, default=12345, help="Random seed for repeatability")
        self.arg_parser.add_argument("-j", "--pieces", type=inkex.Boolean, default=False, help="Make extra pieces for manual boolean separation.")
        self.arg_parser.add_argument("-n", "--smooth_edges", type=inkex.Boolean, default=False, help="Allow pieces with smooth edges.")
        self.arg_parser.add_argument("-f", "--noknob_frequency", type=float, default=10, help="Percentage of smooth-sided edges.")                              
        # dummy for the doc tab - which is named
        self.arg_parser.add_argument("--tab", default="use", help="The selected UI-tab when OK was pressed")
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
            do_smooth = False
            if self.smooth_edges:
                if random.uniform(0.0,100.0) < self.noknob_frequency:
                    do_smooth = True
            if do_smooth:
                pt1 = randomize((startx+i*stepx/2+stepx/2*(i-1), starty), self.random_radius/3, True)
                rand1 = randomize((0, 0), self.random_radius/4, True, True)
                # up to pt1
                ctrl1 = (-self.notch_step*1.5, self.notch_step*1.5)
                clist.extend([pt1[0]+ctrl1[0]-rand1[0], pt1[1]-ctrl1[1]*flip+rand1[1]*flip])
                clist.extend(pt1)
                # last ctrl point for next step
                clist.extend([pt1[0]-ctrl1[0]+rand1[0], pt1[1]+ctrl1[1]*flip-rand1[1]*flip])
            else:
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
        line_style = str(inkex.Style(style))
        attribs = { 'style':line_style, 'id':name, 'd':dirtyFormat(line_path)}
        etree.SubElement(parent, inkex.addNS('path','svg'), attribs )

    def create_horiz_blocks(self, group, gridy, style):
        path = lastpath = 0
        blocks = []
        count = 0
        for node in gridy.iterchildren():
            if node.tag == inkex.addNS('path','svg'): # which they ALL should because we just made them
                path = CubicSuperPath(node.get('d')) # turn it into a global C style SVG path
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
                    n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                else: # internal line - concat a reversed version with the last one
                    thispath = copy.deepcopy(path)
                    for i in range(len(thispath[0])): # reverse the internal C pairs
                        thispath[0][i].reverse()
                    thispath[0].reverse() # reverse the entire line
                    lastpath[0].extend(thispath[0]) # append
                    name = "RowPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':dirtyFormat(lastpath) }
                    n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
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
        n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
        blocks.append(n) # for direct traversal later
        #
        return(blocks)
    

    def create_vert_blocks(self, group, gridx, style):
        path = lastpath = 0
        blocks = []
        count = 0
        for node in gridx.iterchildren():
            if node.tag == inkex.addNS('path','svg'): # which they ALL should because we just made them
                path = CubicSuperPath(node.get('d')) # turn it into a global C style SVG path
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
                    n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
                    blocks.append(n) # for direct traversal later
                else: # internal line - concat a reversed version with the last one
                    thispath = copy.deepcopy(path)
                    for i in range(len(thispath[0])): # reverse the internal C pairs
                        thispath[0][i].reverse()
                    thispath[0].reverse() # reverse the entire line
                    lastpath[0].extend(thispath[0]) # append
                    name = "ColPieces_%d" % (count)
                    attribs = { 'style':style, 'id':name, 'd':dirtyFormat(lastpath) }
                    n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
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
        n = etree.SubElement(group, inkex.addNS('path','svg'), attribs )
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
        jigsaw_pieces = etree.SubElement(jigsaw, 'g', g_attribs)
        line_style = str(inkex.Style(self.line_style))
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
            node.apply_transform()
        for node in yblocks:
            node.set('transform', 'translate(%f,%f)' % (self.width, 0))
            node.apply_transform()

        
    ###--------------------------------------------
    ### The main function called by the Inkscape UI
    def effect(self):
        # document dimensions (for centering)
        docW = self.svg.unittouu(self.document.getroot().get('width'))
        docH = self.svg.unittouu(self.document.getroot().get('height'))
        # extract fields from UI
        self.width  = self.svg.unittouu( str(self.options.width)  + self.options.units )
        self.height  = self.svg.unittouu( str(self.options.height) + self.options.units )
        self.pieces_W = self.options.pieces_W
        self.pieces_H = self.options.pieces_H
        average_block = (self.width/self.pieces_W + self.height/self.pieces_H) / 2
        self.notch_step = average_block * self.options.notch_percent / 3 # 3 = a useful notch size factor
        self.smooth_edges = self.options.smooth_edges
        self.noknob_frequency = self.options.noknob_frequency          
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
        jigsaw_group = etree.SubElement(self.svg.get_current_layer(), 'g', g_attribs)
        #Group for X grid
        g_attribs = {inkex.addNS('label','inkscape'):'X_Gridlines'}
        gridx = etree.SubElement(jigsaw_group, 'g', g_attribs)
        #Group for Y grid
        g_attribs = {inkex.addNS('label','inkscape'):'Y_Gridlines'}
        gridy = etree.SubElement(jigsaw_group, 'g', g_attribs)

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
                node.set('transform', 'translate(%f,%f) rotate(90)' % (self.width, 0))
        # center the jigsaw
        jigsaw_group.set('transform', 'translate(%f,%f)' % ( (docW-self.width)/2, (docH-self.height)/2 ) )
        
        # pieces
        if self.pieces:
            self.create_pieces(jigsaw_group, gridx,gridy)
            # needs manual boolean ops until that is exposed or we get all the commented code working up top :-(
       
if __name__ == '__main__':
	e = LasercutJigsaw()
	e.run()
