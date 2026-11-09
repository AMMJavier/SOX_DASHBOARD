def extract_all_vpn_objects(client):

    all_objects = []

    limit = 50
    offset = 0


    while True:

        print(
            f"Consultando registros {offset} - {offset + limit}"
        )


        response = client.call_api(
            "show-users",
            {
                "details-level": "full",
                "limit": limit,
                "offset": offset
            }
        )


        objects = response.get(
            "objects",
            []
        )


        all_objects.extend(objects)


        total = response.get(
            "total",
            0
        )


        print(
            f"Recibidos: {len(objects)} | "
            f"Acumulados: {len(all_objects)} de {total}"
        )


        if len(all_objects) >= total:
            break


        offset += limit


    return all_objects