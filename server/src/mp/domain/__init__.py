"""Domain layer: players, rooms, matchmaking, and server state.

Named ``domain`` (not ``platform``) so it never shadows the standard-library
``platform`` module that tools like uvicorn import -- which would otherwise
break ``uvicorn mp.main:app`` depending on the startup directory.
"""
