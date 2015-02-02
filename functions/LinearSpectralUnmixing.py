import numpy as np

class LinearSpectralUnmixing():
    def __init__(self):
        self.name = 'Linear Spectral Unmixing'
        self.description = 'Performs linear spectral unmixing for a multiband raster.'
        self.signatures = '{}'


    def getParameterInfo(self):
        return [
            {
                'name': 'raster',
                'dataType': 'raster',
                'value': None,
                'required': True,
                'displayName': 'Raster',
                'description': 'The primary multi-band input raster to be classified'
            },
            {
                'name': 'signatures',
                'dataType': 'string',
                'value': '{\'Veg\': [16.91479, 19.83083, 14.53383,93.16165, 41.97619, 18.11779],'+
                    ' \'Shadow\': [17.78413, 11.62528, 5.50679, 8.22514, 0.72993, 0.14649],'+
                    ' \'NPV\': [17.45967, 17.11275, 16.30269, 26.19254, 40.90807, 45.67303],'+
                    ' \'Soil\': [50.17609, 60.45217, 67.33043,83.83261, 93.41739, 81.16739]}',
                'required': True,
                'displayName': 'Endmember Training Signature Means',
                'description': 'The training site means per each classification for each band'
            },
        ]


    def getConfiguration(self, **scalars):
        return {
            'compositeRasters': False,
            'inheritProperties': 1 | 2| 4 | 8,    # inherit all from the raster
            'invalidateProperties': 2 | 4 | 8,    # reset stats, histogram, key properties
            'inputMask': False                    # no input raster mask
        }


    def updateRasterInfo(self, **kwargs):
        signatures = kwargs['signatures'] # get endmember input string value
        self.signatures = eval(signatures) # convert to python dict

        # output bandCount is number of endmembers + 1 residuals raster
        bandCount = len(self.signatures) + 1

        kwargs['output_info']['bandCount'] = bandCount
        kwargs['output_info']['statistics'] = ()
        kwargs['output_info']['histogram'] = ()
        kwargs['output_info']['pixelType'] = 'f4'

        return kwargs


    def updatePixels(self, tlc, shape, props, **pixelBlocks):
        # convert endmember signature means into arrays of each endmember across bands
        # [[vegB, vegG, vegR, ...], [shadowB, shadowG, shadowR, ...], [...]]
        signatures = np.array(self.signatures.values())

        # transpose axes to into arrays of each band's endmembers
        # [[vegB, shadowB, npvB, ...], [vegG, shadowG, npvG, ...], [...]]
        signaturesT = signatures.T

        # get the input raster pixel block
        inBlock = pixelBlocks['raster_pixels']

        # transpose image array axes into arrays of band values per pixel,
        # [B, G, R, NIR1, SWIR1, SWIR2] at each pixel
        inBlockT = inBlock.transpose([1, 2, 0])
        # reshape to slightly flatten to 2d array
        inBlockTFlat = inBlockT.reshape((-1, inBlockT.shape[-1]))

        # solve simultaneous functions at each pixel stack
        # looping and output of new array of all lstsq results
        def unmixPixel(pixelStack, sigs):
            solution = np.linalg.lstsq(sigs, pixelStack)
            results = np.append(solution[0], solution[1][0]) # return endmembers and residual
            return results

        # np.apply_along_axis seems to be slower than native Python looping
        outBlock = np.apply_along_axis(unmixPixel, 1, inBlockTFlat, signaturesT)

        # outBlock shape is (n, 4); must reconstruct into endmember bands with values in correct x,y
        # e.g. you can reconstruct:  inBlockTFlat.reshape((1994,2310,6)) back to inBlockT
        # here we need (1994,2310,4) without residuals; (1994,2310,5) with residuals
        outBlockReshaped = outBlock.reshape(-1, inBlock.shape[-1], 5).transpose((2,0,1))

        pixelBlocks['output_pixels'] = outBlockReshaped.astype(props['pixelType'])
        return pixelBlocks


    def updateKeyMetadata(self, names, bandIndex, **keyMetadata):
        if bandIndex == -1:
            # dataset level
            keyMetadata['datatype'] = 'Processed'
        elif bandIndex == len(self.signatures):
            # residuals raster
            keyMetadata['wavelengthmin'] = None
            keyMetadata['wavelengthmax'] = None
            keyMetadata['bandname'] = 'Residuals'
        else:
            keyMetadata['wavelengthmin'] = None
            keyMetadata['wavelengthmax'] = None
            keyMetadata['bandname'] = self.signatures.keys()[bandIndex]
        return keyMetadata
