from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import requests
from backend.core.config import settings
from backend.core.auth import get_current_user
# from backend.database.models import User  # Commented out - not used in this file

router = APIRouter()

class LocationRequest(BaseModel):
    address: str

class LocationData(BaseModel):
    address: str
    lat: float
    lng: float
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

class GeocodeResponse(BaseModel):
    success: bool
    data: Optional[LocationData] = None
    error: Optional[str] = None

class AutocompleteRequest(BaseModel):
    input: str
    types: Optional[List[str]] = ["geocode"]

class AutocompletePrediction(BaseModel):
    place_id: str
    description: str
    structured_formatting: dict

class AutocompleteResponse(BaseModel):
    success: bool
    predictions: List[AutocompletePrediction] = []
    error: Optional[str] = None

@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(
    request: LocationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Geocode an address using Google Maps Geocoding API
    """
    try:
        if not settings.GOOGLE_MAPS_API_KEY:
            raise HTTPException(
                status_code=500, 
                detail="Google Maps API key not configured"
            )
        
        # Make request to Google Maps Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": request.address,
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data["status"] != "OK" or not data.get("results"):
            return GeocodeResponse(
                success=False,
                error=f"Geocoding failed: {data.get('status', 'Unknown error')}"
            )
        
        result = data["results"][0]
        location = result["geometry"]["location"]
        
        # Extract address components
        address_components = result.get("address_components", [])
        city = None
        state = None
        country = None
        postal_code = None
        
        for component in address_components:
            types = component.get("types", [])
            if "locality" in types:
                city = component["long_name"]
            elif "administrative_area_level_1" in types:
                state = component["short_name"]
            elif "country" in types:
                country = component["long_name"]
            elif "postal_code" in types:
                postal_code = component["long_name"]
        
        location_data = LocationData(
            address=result["formatted_address"],
            lat=location["lat"],
            lng=location["lng"],
            city=city,
            state=state,
            country=country,
            postal_code=postal_code
        )
        
        return GeocodeResponse(success=True, data=location_data)
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Google Maps API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Geocoding error: {str(e)}"
        )

@router.post("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete_places(
    request: AutocompleteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get place autocomplete suggestions using Google Maps Places API
    """
    try:
        if not settings.GOOGLE_MAPS_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Google Maps API key not configured"
            )
        
        # Make request to Google Maps Places Autocomplete API
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": request.input,
            "types": "|".join(request.types),
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data["status"] not in ["OK", "ZERO_RESULTS"]:
            return AutocompleteResponse(
                success=False,
                error=f"Autocomplete failed: {data.get('status', 'Unknown error')}"
            )
        
        predictions = []
        for prediction in data.get("predictions", []):
            predictions.append(AutocompletePrediction(
                place_id=prediction["place_id"],
                description=prediction["description"],
                structured_formatting=prediction.get("structured_formatting", {})
            ))
        
        return AutocompleteResponse(success=True, predictions=predictions)
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Google Maps API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Autocomplete error: {str(e)}"
        )

@router.get("/place/{place_id}", response_model=GeocodeResponse)
async def get_place_details(
    place_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get detailed information about a place using its place_id
    """
    try:
        if not settings.GOOGLE_MAPS_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Google Maps API key not configured"
            )
        
        # Make request to Google Maps Place Details API
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "formatted_address,geometry,address_components",
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data["status"] != "OK" or not data.get("result"):
            return GeocodeResponse(
                success=False,
                error=f"Place details failed: {data.get('status', 'Unknown error')}"
            )
        
        result = data["result"]
        location = result["geometry"]["location"]
        
        # Extract address components
        address_components = result.get("address_components", [])
        city = None
        state = None
        country = None
        postal_code = None
        
        for component in address_components:
            types = component.get("types", [])
            if "locality" in types:
                city = component["long_name"]
            elif "administrative_area_level_1" in types:
                state = component["short_name"]
            elif "country" in types:
                country = component["long_name"]
            elif "postal_code" in types:
                postal_code = component["long_name"]
        
        location_data = LocationData(
            address=result["formatted_address"],
            lat=location["lat"],
            lng=location["lng"],
            city=city,
            state=state,
            country=country,
            postal_code=postal_code
        )
        
        return GeocodeResponse(success=True, data=location_data)
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Google Maps API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Place details error: {str(e)}"
        )

@router.get("/reverse-geocode")
async def reverse_geocode(
    lat: float,
    lng: float,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Reverse geocode coordinates to get address
    """
    try:
        if not settings.GOOGLE_MAPS_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Google Maps API key not configured"
            )
        
        # Make request to Google Maps Reverse Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{lat},{lng}",
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data["status"] != "OK" or not data.get("results"):
            return GeocodeResponse(
                success=False,
                error=f"Reverse geocoding failed: {data.get('status', 'Unknown error')}"
            )
        
        result = data["results"][0]
        location = result["geometry"]["location"]
        
        # Extract address components
        address_components = result.get("address_components", [])
        city = None
        state = None
        country = None
        postal_code = None
        
        for component in address_components:
            types = component.get("types", [])
            if "locality" in types:
                city = component["long_name"]
            elif "administrative_area_level_1" in types:
                state = component["short_name"]
            elif "country" in types:
                country = component["long_name"]
            elif "postal_code" in types:
                postal_code = component["long_name"]
        
        location_data = LocationData(
            address=result["formatted_address"],
            lat=location["lat"],
            lng=location["lng"],
            city=city,
            state=state,
            country=country,
            postal_code=postal_code
        )
        
        return GeocodeResponse(success=True, data=location_data)
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Google Maps API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reverse geocoding error: {str(e)}"
        )