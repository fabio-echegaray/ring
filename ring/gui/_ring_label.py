import math
import logging

import numpy as np
from PyQt5 import Qt, QtCore, QtGui
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QFont
from PyQt5.QtWidgets import QLabel
from skimage import draw

from ring.measure import Measure
from ring.filters import nucleus


def distance(a, b):
    return np.sqrt((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2)


def is_between(c, a, b):
    dist = distance(a, c) + distance(c, b) - distance(a, b)
    return math.isclose(dist, 0, abs_tol=1)


# noinspection PyPep8Naming
class RingImageQLabel(QLabel, Measure):
    log = logging.getLogger('RingImageQLabel')
    clicked = Qt.pyqtSignal()
    lineUpdated = Qt.pyqtSignal()
    linePicked = Qt.pyqtSignal()
    nucleusPicked = Qt.pyqtSignal()

    def __init__(self, parent):
        super(QLabel, self).__init__(parent=parent)
        super(Measure, self).__init__()
        self.selected = True
        self.dataHasChanged = False
        self.resolution = None
        self.imagePixmap = None
        self.nd = None

        self._activeCh = "dna"

        self._render = True
        self._selNuc = None
        self.currNucleusId = None
        self.mousePos = Qt.QPoint(0, 0)
        self._selectedLine = None
        self.measureLocked = False

        self.setMouseTracking(True)
        self.clear()

    @property
    def currNucleus(self):
        # print(self.nucleus(self.currNucleusId))
        return self.nucleus(self.currNucleusId)["value"].iloc[0]

    @property
    def activeCh(self):
        return self._activeCh

    @activeCh.setter
    def activeCh(self, value):
        if value is not None:
            self._activeCh = value
            self._repaint()

    @property
    def selectedLine(self):
        return self._selectedLine['li'].iloc[0] if self._selectedLine is not None else None

    @selectedLine.setter
    def selectedLine(self, value):
        if type(value) == dict:
            self._selectedLine = value
        elif np.isscalar(value):
            nuclines = self.lines(self.currNucleusId)
            self._selectedLine = nuclines[nuclines["li"] == value]
            self._repaint()
        else:
            self._selectedLine = None

    @property
    def renderMeasurements(self):
        return self._render

    @renderMeasurements.setter
    def renderMeasurements(self, value):
        if value is not None:
            self._render = value
            self._repaint()
            self.setMouseTracking(self._render)

    @Measure.zstack.setter
    def zstack(self, value):
        super(RingImageQLabel, type(self)).zstack.fset(self, value)
        self._repaint()

    @Measure.dnaChannel.setter
    def dnaChannel(self, value):
        super(RingImageQLabel, type(self)).dnaChannel.fset(self, value)
        if self._selNuc is not None:
            if self.activeCh == "dna":
                self._repaint()

    @Measure.rngChannel.setter
    def rngChannel(self, value):
        super(RingImageQLabel, type(self)).rngChannel.fset(self, value)
        if self.activeCh == "act":
            self._repaint()

    @Measure.file.setter
    def file(self, file):
        if file is not None:
            self.log.info('Loading %s' % file)
            super(RingImageQLabel, type(self)).file.fset(self, file)
            self._repaint()

    def clear(self):
        imgarr = np.zeros(shape=(512, 512), dtype=np.uint32)
        qtimage = QtGui.QImage(imgarr.data, imgarr.shape[1], imgarr.shape[0], imgarr.strides[0],
                               QtGui.QImage.Format_RGB32)
        self.imagePixmap = QtGui.QPixmap(qtimage)
        self.setPixmap(self.imagePixmap)

    def _repaint(self):
        self.dataHasChanged = True
        self.update()

    def mouseMoveEvent(self, event):
        # self.log.debug('mouseMoveEvent')
        if self.file is None:
            return

        if not self.measureLocked and event.type() == QtCore.QEvent.MouseMove and not self.lines().empty:
            if event.buttons() == QtCore.Qt.NoButton:
                pos = event.pos()
                # convert to image pixel coords
                x = int(pos.x() * self.dwidth / self.width())
                y = int(pos.y() * self.dheight / self.height())
                self.mousePos = Qt.QPoint(x, y)

                # print("------------------------------------------------------")
                for ix, me in self.lines(self.currNucleusId).iterrows():
                    pts = [Qt.QPoint(x, y) for x, y in [me['ls0'], me['ls1']]]
                    # print("X %d %d %d | Y %d %d %d" % (
                    #     min(pts[0].x(), pts[1].x()), self.mousePos.x(), max(pts[0].x(), pts[1].x()),
                    #     min(pts[0].y(), pts[1].y()), self.mousePos.y(), max(pts[0].y(), pts[1].y())))
                    if is_between(self.mousePos, pts[0], pts[1]):
                        if me['li'] != self.selectedLine:
                            self.log.debug(f"Mouse over line {me['li']}.")
                            self.selectedLine = me['li']
                            self.lineUpdated.emit()
                            self._repaint()
                            break

    def mouseReleaseEvent(self, ev):
        if self.file is None:
            return

        pos = ev.pos()
        # convert to image pixel coords
        x = int(pos.x() * self.dwidth / self.width())
        y = int(pos.y() * self.dheight / self.height())
        self.log.debug(f'Clicked on (x,y)=({x},{y})')

        anyLineSelected = False
        lineChanged = False
        if not self.lines().empty:
            for ix, me in self.lines().iterrows():
                pts = [Qt.QPoint(x, y) for x, y in [me['ls0'], me['ls1']]]
                if is_between(self.mousePos, pts[0], pts[1]):
                    anyLineSelected = True
                    if me['li'] != self.selectedLine:
                        lineChanged = True
                        self.selectedLine = me['li']
                        self.log.debug(f"Mouse click over line {me['li']}.")
                        break

        # check if pointer clicked inside any nuclei
        nucleus = self.nucleus(x, y)
        if nucleus.empty:
            return

        if len(nucleus) == 1:
            item = nucleus.iloc[0]
            nid = int(item['id'])
            nuc = item['value']
            self.log.debug(f"Nucleus {nid} selected by clicking.\r\n"
                           f"    Area={nuc.area :.2f}[pix^2]\r\n"
                           f"        ={nuc.area / self.pix_per_um ** 2 :.2f}[um^2],\r\n"
                           f"    equivalent radius={np.sqrt(nuc.area / np.pi):.2f}[pix]\r\n"
                           f"                     ={np.sqrt(nuc.area / np.pi) / self.pix_per_um:.2f}[um].")
            self.lines(nucleus['id'].iloc[0])
            nucbnd = nucleus["value"].iloc[0]
            self._selNuc = nucbnd
            self.currNucleusId = int(nucleus["id"].iloc[0])
            self.nucleusPicked.emit()

        if anyLineSelected and not lineChanged and not self.measureLocked:
            self.clicked.emit()
            self.measureLocked = True
            self.linePicked.emit()
        else:
            self.measureLocked = False
            self._repaint()
            self.clicked.emit()

    def paint_measures(self):
        self.log.debug("Painting measurements.")
        data = self.rngimage

        # map the data range to 0 - 255
        # img8bit = ((data - data.min()) / (data.ptp() / 255.0)).astype(np.uint8)
        img8bit = data

        for _id, me in self.measurements.iterrows():
            if np.isnan(me['ls0']).any() or np.isnan(me['ls1']).any():
                continue
            r0, c0, r1, c1 = np.array(list(me['ls0']) + list(me['ls1'])).astype(int)
            rr, cc = draw.line(r0, c0, r1, c1)
            img8bit[cc, rr] = 255
            rr, cc = draw.circle(r0, c0, 3)
            img8bit[cc, rr] = 255

        qtimage = QtGui.QImage(img8bit.repeat(4), self.dwidth, self.dheight, QtGui.QImage.Format_RGB32)
        self.imagePixmap = QPixmap(qtimage)
        self.setPixmap(self.imagePixmap)
        return

    # @profile
    def paintEvent(self, event):
        if self.dataHasChanged and not (self.rngpixmap is None and self.dnapixmap is None):
            self.dataHasChanged = False
            qpixmap = self.rngpixmap if self.activeCh == "act" else self.dnapixmap

            self.imagePixmap = qpixmap.copy()
            if self.renderMeasurements:
                self._drawMeasurements()
            self.setPixmap(self.imagePixmap)

        return QLabel.paintEvent(self, event)

    def _drawMeasurements(self):
        if self._selNuc is None:
            return

        painter = QPainter()
        painter.begin(self.imagePixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        rng_thick = 3
        rng_thick *= self.pix_per_um

        if self.activeCh == "dna":
            # get nuclei boundary as a polygon
            nucb_qpoints_e = [Qt.QPoint(x, y) for x, y in self._selNuc.buffer(rng_thick).exterior.coords]
            nucb_qpoints_i = [Qt.QPoint(x, y) for x, y in self._selNuc.exterior.coords]

            painter.setPen(QPen(QBrush(QColor('white')), 3))
            painter.drawPolygon(Qt.QPolygon(nucb_qpoints_i))
            painter.drawPolygon(Qt.QPolygon(nucb_qpoints_e))

            nucb_poly = Qt.QPolygon(nucb_qpoints_e).subtracted(Qt.QPolygon(nucb_qpoints_i))
            brush = QBrush(QtCore.Qt.BDiagPattern)
            brush.setColor(QColor('white'))
            painter.setBrush(brush)
            painter.setPen(QPen(QBrush(QColor('transparent')), 0))

            painter.drawPolygon(nucb_poly)

        elif self.activeCh == "act":
            nuc_pen = QPen(QBrush(QColor('red')), self.dwidth / 256)
            nuc_pen.setStyle(QtCore.Qt.DotLine)
            painter.setPen(nuc_pen)
            for i, e in self.nuclei.iterrows():
                n = e["value"]
                if e["id"] == self.currNucleusId:
                    brush = QBrush(QtCore.Qt.BDiagPattern)
                    brush.setColor(QColor('yellow'))
                    painter.setBrush(brush)

                # get nuclei boundary as a polygon
                nucb_qpoints = [Qt.QPoint(x, y) for x, y in n.exterior.coords]
                painter.drawPolygon(Qt.QPolygon(nucb_qpoints))
                painter.setBrush(QBrush(QtCore.Qt.NoBrush))

        for ix, me in self.lines(self.currNucleusId).iterrows():
            thickness = self.pix_per_um
            thickness *= (2 if (self.selectedLine is not None and
                                self.selectedLine == me['li'])
                          else 1)
            painter.setPen(QPen(QBrush(QColor(me['c'])), thickness))
            pts = [Qt.QPoint(x, y) for x, y in [me['ls0'], me['ls1']]]
            painter.drawLine(pts[0], pts[1])

        painter.setPen(QPen(QBrush(QColor('red')), 3))
        painter.setFont(QFont("arial", 60))
        for ix, nrow in self.nuclei.pipe(nucleus,
                                         nucleus_col='value',
                                         radius_min=5 * self.pix_per_um,
                                         radius_max=13.5 * self.pix_per_um).iterrows():
            nuc = nrow["value"]
            painter.drawText(nuc.centroid.x, nuc.centroid.y, f"{int(nrow['id'])}")

        painter.end()
