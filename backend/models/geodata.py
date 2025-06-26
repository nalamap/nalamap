from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from typing import NamedTuple
from pydantic import BaseModel


class DataType(str, Enum):
    GEOJSON = "GeoJson"
    LAYER = "Layer"
    UPLOADED = "uploaded"


class DataOrigin(Enum):
    UPLOAD = "uploaded"
    TOOL = "tool"
    GEPROCESSING = "geprocessing"


class GeoDataIdentifier(NamedTuple):
    id: str
    data_source_id: str


@dataclass
class LayerStyle:
    """Enhanced style configuration for different geometry types"""
    # Common stroke properties for all geometry types
    stroke_color: Optional[str] = "#3388ff"
    stroke_weight: Optional[float] = 2
    stroke_opacity: Optional[float] = 1.0
    stroke_dash_array: Optional[str] = None  # e.g., "5,5" for dashed lines
    stroke_dash_offset: Optional[float] = None
    
    # Fill properties for polygons and circles
    fill_color: Optional[str] = "#3388ff"
    fill_opacity: Optional[float] = 0.3
    fill_pattern: Optional[str] = None  # For pattern fills (future enhancement)
    
    # Point/marker specific properties
    radius: Optional[float] = 8
    marker_symbol: Optional[str] = None  # For custom markers (future enhancement)
    
    # Line-specific properties
    line_cap: Optional[str] = "round"  # "round", "square", "butt"
    line_join: Optional[str] = "round"  # "round", "bevel", "miter"
    
    # Advanced visual properties
    blur: Optional[float] = None  # Gaussian blur effect
    shadow_color: Optional[str] = None  # Drop shadow color
    shadow_offset_x: Optional[float] = None  # Shadow offset
    shadow_offset_y: Optional[float] = None  # Shadow offset
    shadow_blur: Optional[float] = None  # Shadow blur radius
    
    # Animation properties (future enhancement)
    animation_duration: Optional[float] = None  # Animation duration in seconds
    animation_type: Optional[str] = None  # "pulse", "spin", "bounce", etc.
    
    # Conditional styling (future enhancement)
    style_conditions: Optional[Dict[str, Any]] = None  # For data-driven styling

class GeoDataObject(BaseModel):
    # Required (key) fields
    id: str
    data_source_id: str  # e.g. database name
    data_type: DataType
    data_origin: str

    # Required metadata
    data_source: str  # e.g. portal name
    data_link: str
    name: str

    # Optional fields
    title: Optional[str] = None
    description: Optional[str] = None
    llm_description: Optional[str] = None
    score: Optional[float] = None
    bounding_box: Optional[str] = None
    layer_type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = {}

    visible: Optional[bool] = False
    selected: Optional[bool] = False
    style: Optional[LayerStyle] = None

    class Config:
        # Allow Enum values to be output as raw values
        use_enum_values = True
        # Any extra fields in input will be ignored
        extra = "ignore"


def mock_geodata_objects() -> List[GeoDataObject]:
    return [
        GeoDataObject(
            id="1512",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="AQUAMAPS",
            data_link="https://io.apps.fao.org/geoserver/wms/wms?service=WMS&request=GetMap&layers=AQUAMAPS:rivers_africa&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="AQUAMAPS:rivers_africa",
            title="Rivers of Africa (Derived from HydroSHEDS)",
            description="""The rivers of Africa dataset is derived from the World Wildlife Fund's (WWF) HydroSHEDS drainage direction layer and a stream network layer. The source of the drainage direction layer was the 15-second Digital Elevation Model (DEM) from NASA's Shuttle Radar Topographic Mission (SRTM). The raster stream network was determined by using the HydroSHEDS flow accumulation grid, with a threshold of about 1000 km² upstream area.

    The stream network dataset consists of the following information: the origin node of each arc in the network (FROM_NODE), the destination of each arc in the network (TO_NODE), the Strahler stream order of each arc in the network (STRAHLER), numerical code and name of the major basin that the arc falls within (MAJ_BAS and MAJ_NAME); - area of the major basin in square km that the arc falls within (MAJ_AREA); - numerical code and name of the sub-basin that the arc falls within (SUB_BAS and SUB_NAME); - area of the sub-basin in square km that the arc falls within (SUB_AREA); - numerical code of the sub-basin towards which the sub-basin flows that the arc falls within (TO_SUBBAS) (the codes -888 and -999 have been assigned respectively to internal sub-basins and to sub-basins draining into the sea). 
    The attributes table now includes a field named "Regime" with tentative classification of perennial ("P") and intermittent ("I") streams.

    **Supplemental Information:**

    This dataset is developed as part of a GIS-based information system on water resources for the African continent. It has been published in the framework of the AQUASTAT - programme of the Land and Water Division of the Food and Agriculture Organization of the United Nations.

    **Contact points:**

    Metadata Contact: AQUASTAT <aquastat@fao.org>
    Resource Contact: Jippe Hoogeveen <Jippe.Hoogeveen@fao.org>, Livia Peiser <Livia.Peiser@fao.org>

    **Data lineage:**

    The linework of the map was obtained by converting the stream network to a feature dataset with the Hydrology toolset in ESRI ArcGIS. The Flow Direction and Stream Order grids were derived from hydrologically corrected elevation data with a resolution of 15 arc-seconds. The elevation dataset was part of a mapping product, HydroSHEDS, developed by the Conservation Science Program of World Wildlife Fund. Original input data had been obtained during NASA's Shuttle Radar Topography Mission (SRTM).

    **Online resources:**

    - Download - Rivers of Africa (ESRI shapefile): https://storage.googleapis.com/fao-maps-catalog-data/geonetwork/aquamaps/rivers_africa_37333.zip
    - Hydrological basins in Africa: https://data.apps.fao.org/catalog/dataset/e54e2014-d23b-402b-8e73-c827628d17f4
    - Rivers data documentation (PDF): https://storage.googleapis.com/fao-maps-catalog-data/geonetwork/aquamaps/Aquamaps-River_Data_description.pdf
    - HydroSHEDS: http://www.worldwildlife.org/hydrosheds
    - HydroSHEDS tech info: https://www.hydrosheds.org
    """,
            llm_description="The \"Rivers of Africa\" dataset, derived from the World Wildlife Fund's HydroSHEDS, provides a comprehensive stream network for the African continent. Utilizing a 15-second Digital Elevation Model (DEM) from NASA's Shuttle Radar Topographic Mission (SRTM), this dataset offers detailed hydrological information, including drainage directions and stream orders. The stream network is characterized by attributes such as origin and destination nodes, Strahler stream order, and basin information, including major and sub-basin codes, names, and areas. Additionally, the dataset classifies streams as perennial or intermittent. Developed as part of the AQUASTAT program by the FAO's Land and Water Division, this dataset supports GIS-based water resource management across Africa. The bounding box for this dataset spans from approximately 54.35°E to -17.24°E longitude and -34.76°S to 37.22°N latitude, covering a significant portion of the continent.",
            score=0.13876973,
            bounding_box="POLYGON((54.34999999999883 -34.76458333333335,54.34999999999883 37.21874999999888,-17.23958333333337 37.21874999999888,-17.23958333333337 -34.76458333333335,54.34999999999883 -34.76458333333335))",
            layer_type="WMS",
            properties={"resource_id": "1512", "format": None},
        ),
        GeoDataObject(
            id="2180",
            data_source_id="db_name",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,
            data_source="AQUAMAPS",
            data_link="https://io.apps.fao.org/geoserver/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=AQUAMAPS:rivers_africa&outputFormat=application/json",
            name="AQUAMAPS:rivers_africa",
            title="Rivers of Africa (Derived from HydroSHEDS)",
            description="""The rivers of Africa dataset is derived from the World Wildlife Fund's (WWF) HydroSHEDS drainage direction layer and a stream network layer. The source of the drainage direction layer was the 15-second Digital Elevation Model (DEM) from NASA's Shuttle Radar Topographic Mission (SRTM). The raster stream network was determined by using the HydroSHEDS flow accumulation grid, with a threshold of about 1000 km² upstream area.

    The stream network dataset consists of the following information: the origin node of each arc in the network (FROM_NODE), the destination of each arc in the network (TO_NODE), the Strahler stream order of each arc in the network (STRAHLER), numerical code and name of the major basin that the arc falls within (MAJ_BAS and MAJ_NAME); - area of the major basin in square km that the arc falls within (MAJ_AREA); - numerical code and name of the sub-basin that the arc falls within (SUB_BAS and SUB_NAME); - area of the sub-basin in square km that the arc falls within (SUB_AREA); - numerical code of the sub-basin towards which the sub-basin flows that the arc falls within (TO_SUBBAS) (the codes -888 and -999 have been assigned respectively to internal sub-basins and to sub-basins draining into the sea). 
    The attributes table now includes a field named "Regime" with tentative classification of perennial ("P") and intermittent ("I") streams.

    **Supplemental Information:**

    This dataset is developed as part of a GIS-based information system on water resources for the African continent. It has been published in the framework of the AQUASTAT - programme of the Land and Water Division of the Food and Agriculture Organization of the United Nations.

    **Contact points:**

    Metadata Contact: AQUASTAT <aquastat@fao.org>
    Resource Contact: Jippe Hoogeveen <Jippe.Hoogeveen@fao.org>, Livia Peiser <Livia.Peiser@fao.org>

    **Data lineage:**

    The linework of the map was obtained by converting the stream network to a feature dataset with the Hydrology toolset in ESRI ArcGIS. The Flow Direction and Stream Order grids were derived from hydrologically corrected elevation data with a resolution of 15 arc-seconds. The elevation dataset was part of a mapping product, HydroSHEDS, developed by the Conservation Science Program of World Wildlife Fund. Original input data had been obtained during NASA's Shuttle Radar Topography Mission (SRTM).

    **Online resources:**

    - Download - Rivers of Africa (ESRI shapefile): https://storage.googleapis.com/fao-maps-catalog-data/geonetwork/aquamaps/rivers_africa_37333.zip
    - Hydrological basins in Africa: https://data.apps.fao.org/catalog/dataset/e54e2014-d23b-402b-8e73-c827628d17f4
    - Rivers data documentation (PDF): https://storage.googleapis.com/fao-maps-catalog-data/geonetwork/aquamaps/Aquamaps-River_Data_description.pdf
    - HydroSHEDS: http://www.worldwildlife.org/hydrosheds
    - HydroSHEDS tech info: https://www.hydrosheds.org
    """,
            llm_description="The \"Rivers of Africa\" dataset provides a comprehensive representation of the continent's river networks, derived from the World Wildlife Fund's HydroSHEDS drainage direction layer and stream network data. Utilizing a 15-second Digital Elevation Model (DEM) from NASA's Shuttle Radar Topographic Mission (SRTM), this dataset offers detailed insights into Africa's hydrological features. The stream network is delineated using a flow accumulation grid with a threshold of approximately 1000 km² upstream area, ensuring accurate depiction of river courses. Key attributes include the origin and destination nodes of each river arc, Strahler stream order, and basin information such as major and sub-basin codes, names, and areas. Additionally, the dataset classifies streams as perennial or intermittent. Developed as part of a GIS-based water resources information system for Africa, this dataset supports the AQUASTAT program by the FAO's Land and Water Division. The dataset is accessible in various formats, including ESRI shapefiles, and is supported by extensive documentation and resources for further exploration. The bounding box covers a wide geographical area from approximately 54.35°E to -17.24°E longitude and -34.76°S to 37.22°N latitude, encompassing diverse African river systems.",
            score=0.14160219,
            bounding_box="POLYGON((54.34999999999883 -34.76458333333335,54.34999999999883 37.21874999999888,-17.23958333333337 37.21874999999888,-17.23958333333337 -34.76458333333335,54.34999999999883 -34.76458333333335))",
            layer_type="WFS",
            properties={"resource_id": "2180", "format": None},
        ),
        GeoDataObject(
            id="1866",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="HOTOSM",
            data_link="https://data.apps.fao.org/map/gsrv/edit/casap/ows?service=WMS&request=GetMap&layers=rivieres_principales_hotosm_fao&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="rivieres_principales_hotosm_fao",
            title="rivieres_principales_hotosm_fao",
            description="""Rivières principales de la République Centrafricaine. Le fichier est une sélection du HOTOSM Central African Republic Waterways (OpenStreetMap Export) distribué par OCHA à travers le portail Humanitarian Data Exchange. Les cours d'eau ont été integré pour guarantir la continuité des lignes.

    **Data publication:** 2023-02-25

    **Contact points:**
    Resource Contact: Matieu Henry <matieu.henry@fao.org>, Simone Maffei FAO-UN
    Metadata Contact: FAO-NSL Geospatial Unit <gis-manager@fao.org>

    **Resource constraints:**
    Open Database License (ODC-ODbL)
    """,
            llm_description='The "rivieres_principales_hotosm_fao" dataset provides a detailed representation of the main rivers in the Central African Republic. Derived from the HOTOSM Central African Republic Waterways, this dataset ensures continuity of river lines and is distributed under the ODC-ODbL license. Geographic coverage spans approximately 2.23°N–11.01°N latitude and 14.40°E–27.45°E longitude.',
            score=0.15012261,
            bounding_box="POLYGON((27.4488258 2.2256092,27.4488258 11.0132214040059,14.4023134008397 11.0132214040059,14.4023134008397 2.2256092,27.4488258 2.2256092))",
            layer_type="WMS",
            properties={"resource_id": "1866", "format": None},
        ),
        GeoDataObject(
            id="1718",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="FAO",
            data_link="https://data.apps.fao.org/map/gsrv/edit/wwweeks/ows?service=WMS&request=GetMap&layers=Rivers (Ethiopia)&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="Rivers (Ethiopia)",
            title="Rivers (Ethiopia)",
            description="No notes available",
            llm_description='The "Rivers (Ethiopia)" geospatial dataset provides a comprehensive representation of the river systems within Ethiopia, covering a geographic extent defined by the bounding box coordinates from approximately 3.92° to 14.89° latitude and 32.86° to 45.23° longitude. Accessible via WMS and ideal for hydrological studies.',
            score=0.15421289,
            bounding_box="POLYGON((45.227108897280175 3.924902666646508,45.227108897280175 14.88983906218417,32.8600492633985 14.88983906218417,32.8600492633985 3.924902666646508,45.227108897280175 3.924902666646508))",
            layer_type="WMS",
            properties={"resource_id": "1718", "format": None},
        ),
        GeoDataObject(
            id="1993",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="FAO",
            data_link="https://data.apps.fao.org/map/gsrv/edit/wwweek/ows?service=WMS&request=GetMap&layers=Rivers (Ethiopia)&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="Rivers (Ethiopia)",
            title="Rivers (Ethiopia)",
            description="No notes available",
            llm_description='The "Rivers (Ethiopia)" dataset maps river systems across Ethiopia, supporting environmental management and planning, covering approximately 3.92°–14.89°N latitude and 32.86°–45.23°E longitude.',
            score=0.15872921,
            bounding_box="POLYGON((45.227108897280175 3.924902666646508,45.227108897280175 14.88983906218417,32.8600492633985 14.88983906218417,32.8600492633985 3.924902666646508,45.227108897280175 3.924902666646508))",
            layer_type="WMS",
            properties={"resource_id": "1993", "format": None},
        ),
        GeoDataObject(
            id="2012",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="FAO",
            data_link="https://data.apps.fao.org/map/gsrv/edit/Terria_WA_proj/ows?service=WMS&request=GetMap&layers=main rivers in Rwanda&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="main rivers in Rwanda",
            title="main rivers in Rwanda",
            description="No notes available",
            llm_description='The "Main Rivers in Rwanda" dataset provides a detailed representation of the primary river systems within Rwanda, covering approximately 29.56°–30.78°E longitude and -2.57°–-1.38°S latitude. Accessible via WMS.',
            score=0.15911782,
            bounding_box="POLYGON((30.78125 -2.57292,30.78125 -1.38333,29.56458 -1.38333,29.56458 -2.57292,30.78125 -2.57292))",
            layer_type="WMS",
            properties={"resource_id": "2012", "format": None},
        ),
        GeoDataObject(
            id="1623",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="WWF HydroSHEDS",
            data_link="https://data.apps.fao.org/map/gsrv/edit/adb_awash/ows?service=WMS&request=GetMap&layers=awash_rivers&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="awash_rivers",
            title="awash_rivers",
            description="""Awash river is derived from the HydroRIVERS product, which was obtained by delineating river networks from hydrologically corrected elevation data (WWF HydroSHEDS, Lehner et al. 2008; Lehner and Grill 2013). The Awash river, as well as any other river within the HydroRIVERS database, is co-registered to the sub-basin of the HydroBASINS database in which it resides (via a shared ID).

    **Data publication:** 2020-01-01

    **Citation:** FAO 2018. WaPOR Database Methodology: Level 3. Remote Sensing for Water Productivity Technical Report: Methodology Series. Rome, FAO. 72 pages. Licence: CC BY-NC-SA 3.0 IGO

    **Contact points:** Metadata Contact: Solomon Seyoum <s.seyoum@un-ihe.org>, Resource Contact: WaPOR <wapor@fao.org>

    **Resource constraints:** Covered by HydroSHEDS License Agreement (https://www.hydrosheds.org).
    """,
            llm_description='The "awash_rivers" dataset represents the Awash River network, derived from HydroRIVERS and co-registered with HydroBASINS sub-basins. Covering approximately 43.10°–38.23°E longitude and 8.14°–12.23°N latitude, this dataset supports hydrological studies and environmental management under the HydroSHEDS License Agreement.',
            score=0.17129919,
            bounding_box="POLYGON((43.1020833333324 8.14374999999932,43.1020833333324 12.2270833333326,38.2312499999991 12.2270833333326,38.2312499999991 8.14374999999932,43.1020833333324 8.14374999999932))",
            layer_type="WMS",
            properties={"resource_id": "1623", "format": None},
        ),
        GeoDataObject(
            id="1511",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="RICCAR",
            data_link="https://io.apps.fao.org/geoserver/wms/wms?service=WMS&request=GetMap&layers=RICCAR:rivers&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="RICCAR:rivers",
            title="Rivers",
            description="""Main rivers over the study area of Mindanao island of Philippines.

    **Data publication:** 2020-01-01

    **Contact points:** Metadata and Resource Contact: Solomon Seyoum <s.seyoum@un-ihe.org>

    **Resource constraints:** copyright
    """,
            llm_description='This geospatial dataset, titled "Rivers," provides a detailed representation of the main rivers across Mindanao Island, Philippines, published on January 1, 2020. Accessible via WMS and subject to copyright.',
            score=0.17454045,
            bounding_box="POLYGON((76.00000000019992 -7.000000000299735,76.00000000019992 45.00000000009999,-16.7080219443572 45.00000000009999,-16.7080219443572 -7.000000000299735,76.00000000019992 -7.000000000299735))",
            layer_type="WMS",
            properties={"resource_id": "1511", "format": None},
        ),
        GeoDataObject(
            id="2119",
            data_source_id="db_name",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,
            data_source="WWF HydroSHEDS",
            data_link="https://data.apps.fao.org/map/gsrv/edit/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=hih_test:Awash_rivers&outputFormat=application/json",
            name="hih_test:Awash_rivers",
            title="Awash_rivers",
            description="""Awash river is derived from the HydroRIVERS product, which was obtained by delineating river networks from hydrologically corrected elevation data (WWF HydroSHEDS, Lehner et al. 2008; Lehner and Grill 2013). The Awash river, as well as any other river within the HydroRIVERS database, is co-registered to the sub-basin of the HydroBASINS database in which it resides (via a shared ID).

    **Data publication:** 2020-01-01

    **Citation:** FAO 2018. WaPOR Database Methodology: Level 3. Remote Sensing for Water Productivity Technical Report: Methodology Series. Rome, FAO. 72 pages. Licence: CC BY-NC-SA 3.0 IGO

    **Contact points:** Metadata Contact: Solomon Seyoum <s.seyoum@un-ihe.org>, Resource Contact: WaPOR <wapor@fao.org>

    **Resource constraints:** Covered by HydroSHEDS License Agreement (https://www.hydrosheds.org).
    """,
            llm_description='The "Awash_rivers" dataset is a geospatial representation of the Awash River network, derived from HydroRIVERS with co-registration to HydroBASINS sub-basins. Covering approximately 43.10°–38.23°E longitude and 8.14°–12.23°N latitude, freely available under the HydroSHEDS License Agreement.',
            score=0.17614436,
            bounding_box="POLYGON((43.104518749999 8.14131458333259,43.104518749999 12.2295187499992,38.2288145833324 12.2295187499992,38.2288145833324 8.14131458333259,43.104518749999 8.14131458333259))",
            layer_type="WFS",
            properties={"resource_id": "2119", "format": None},
        ),
        GeoDataObject(
            id="842",
            data_source_id="db_name",
            data_type=DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source="AQUAMAPS",
            data_link="https://io.apps.fao.org/geoserver/wms/wms?service=WMS&request=GetMap&layers=AQUAMAPS:hydrobasins_africa&format=image/png&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256",
            name="AQUAMAPS:hydrobasins_africa",
            title="Hydrological basins in Africa (Derived from HydroSHEDS)",
            description="""This dataset divides the African continent into major hydrological basins and their sub-basins according to hydrological characteristics, derived from WWF HydroSHEDS and Hydro1K.

    Includes numerical codes, names, areas for major and sub-basins, and flow directions.

    **Supplemental Information:**

    Developed under the AQUASTAT program by FAO's Land and Water Division.

    **Contact points:**

    Metadata Contact: AQUASTAT <aquastat@fao.org>
    Resource Contact: Jippe Hoogeveen <jippe.hoogeveen@fao.org>

    **Data lineage:**

    Delineated from hydrologically corrected elevation data (15″ resolution) from HydroSHEDS.

    **Online resources:**

    - Download shapefile: https://storage.googleapis.com/fao-maps-catalog-data/geonetwork/aquamaps/hydrobasins_africa.zip
    - HydroSHEDS: http://www.worldwildlife.org/hydrosheds
    - HydroSHEDS tech info: https://www.hydrosheds.org/
    """,
            llm_description='The "Hydrological Basins in Africa" dataset provides a comprehensive delineation of major and sub-basins across Africa, derived from WWF HydroSHEDS and Hydro1K. It includes codes, names, areas, and flow directions, supporting hydrological studies and water resource management under the AQUASTAT program.',
            score=0.1765908,
            bounding_box="POLYGON((54.53749999999906 -34.837500000000276,54.53749999999906 37.56249999999858,-18.162499999999717 37.56249999999858,-18.162499999999717 -34.837500000000276,54.53749999999906 -34.837500000000276))",
            layer_type="WMS",
            properties={"resource_id": "842", "format": None},
        ),
    ]
